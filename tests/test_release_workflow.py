"""The workflows' own wiring, watched.

**The property.** Every environment variable a workflow step's script reads is
one of four things: the step assigns it itself, the step's ``env:`` declares
it, the job or the workflow declares it, or GitHub provides it to every step.

**Why it needs watching.** A step that reads a variable nothing gave it does
not say so. It reads the empty string, or it reads whatever happens to be in
the process environment, and the failure surfaces somewhere else entirely: the
file it was going to read is not there, and the error names the file rather
than the missing declaration.

**That is not a hypothetical.** The release gate's licence audit read its
requirements file from a path the step had never been told about, and the run
died with a bare ``FileNotFoundError`` on a file nobody had heard of. The
error said nothing about the thing that was actually wrong, and the fix was a
single line of ``env:`` -- a line no in-repo rule required anyone to write.

**Why the check is on the workflow text and not on the run.** The run *does*
catch it: the step fails, the job goes red, the gate does not pass. What the
run cannot do is catch it before it costs a CI run and a person's afternoon.
This file turns that class of mistake into a local failure, which is the
difference between a red build and a red test.

**And the check itself is watched.** A checker that cannot fail is not a
witness, so the last test in this file feeds it a step that is missing a
declaration and requires it to name the variable.

**The release gate's font list is watched the same way.** The gate refuses a
distribution that carries a font file, and it recognises a font by its
extension. That list had drifted away from the font licence audit: the audit
names reportlab's ``DarkGarden.sfd`` -- the *source* of the one bundled font
that is not permissive -- and the gate did not know that extension, so the
file the audit names could have gone into a source distribution unnoticed.
So the list is compared with the audit's own list, and the gate's own program
is run over a release that carries a font.

**And the paid probe is watched, because a green row that ran nothing is this
repository's recurring failure.** ``provider-smoke.yml`` discharges the
protocol's fifth gate class, and it can only do that where a secret exists --
which is precisely the condition under which a workflow most easily reports
success while running nothing. Four things are therefore required of it: it can
never become a required status check, it refuses before spending when a variable
is empty, it reads a report that distinguishes a skip from a pass rather than
trusting an exit code, and the record it leaves goes to the runner's temp and not
into the checkout. Each is put to a doctored version of the same input as well,
so the checks are shown able to fail.

**The closure the gate audits is watched against NOTICE, in the same file.** The
gate reads every installed distribution's licence and refuses a release whose
closure carries a term it does not record; NOTICE §2.2 prints the census that
audit produces and §2.3 names the four dependencies whose *bundled* material
carries terms of its own. Nothing compared the two, and nothing compared §2.2's
five closure figures -- 171 requirement lines, 167 Linux, 165 macOS, 168 Windows,
a union of 170 -- with anything. They are a computation over the markers
``uv export`` prints for this lock, and the licence file paths §2.3 names are
files inside installed distributions. ``scripts/notice_licence_watch.py`` is the
reader; the cases below run it against the real tree and against doctored copies
of its own outputs, so each is shown able to fail. The gate's labelling is
extracted from this file's own subject rather than re-implemented here: two
copies of the licence normalisation drift, and their disagreement looks like a
licence change.

**And the LGPL delivery record is watched the same way.** NOTICE §2.5.1 promises
a corresponding source for every binary §2.5 records under an LGPL-2.1 term, and
names each one's file, byte count, sha256, upstream URL and the point at which it
is offered. That is a record with legal weight and no artefact behind it yet --
nothing has been released -- so the only thing a witness can hold is the record
itself: that every such binary has an entry, and that each entry states all five
things rather than gesturing at a source. ``scripts/lgpl_source_release.py`` is
the reader, and it is also the tool a release would run, which is why the cases
below call it rather than re-deriving its patterns. The §2.5.1 half of the record
is additionally checked against the bytes of the upstream archives where they are
on hand -- ``LABCAIRN_LGPL_SOURCE_DIR`` names the directory -- and reports itself
as not run where they are not, rather than reporting a hash it never took.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

#: The directory the workflows live in.
WORKFLOW_DIR: Final[Path] = Path(".github") / "workflows"

#: A shell assignment at the start of a line: ``NAME=...`` or ``export NAME=...``.
_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=",
    re.MULTILINE,
)

#: A braced shell reference: ``${NAME}``.
_BRACED: Final[re.Pattern[str]] = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: A bare shell reference: ``$NAME``. The lookbehind keeps ``${{`` -- a GitHub
#: expression -- and ``${`` out of the match.
_BARE: Final[re.Pattern[str]] = re.compile(r"(?<![A-Za-z0-9_$/{])\$([A-Za-z_][A-Za-z0-9_]*)")

#: A Python environment read: ``os.environ["NAME"]`` or
#: ``os.environ.get("NAME", ...)``.
_ENVIRON: Final[re.Pattern[str]] = re.compile(
    r"""os\.environ(?:\.get\(|\[)\s*["']([A-Za-z_][A-Za-z0-9_]*)["']"""
)

#: The variables GitHub puts in every step's environment, and the prefixes it
#: namespaces its own under. A name in this set is never a missing
#: declaration -- it is the platform's, and the platform always sets it.
CI_PROVIDED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "APPDATA",
        "CI",
        "COMSPEC",
        "DEBIAN_FRONTEND",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "LOGNAME",
        "NUMBER_OF_PROCESSORS",
        "OS",
        "PATH",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
        "PROGRAMFILES",
        "PROGRAMDATA",
        "PYTHONHASHSEED",
        "PYTHONIOENCODING",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PWD",
        "SHELL",
        "SSL_CERT_FILE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "TMPDIR",
        "USER",
        "USERPROFILE",
        "VIRTUAL_ENV",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)

CI_PROVIDED_PREFIXES: Final[tuple[str, ...]] = (
    "ACTIONS_",
    "AGENT_",
    "BUILD_",
    "GITHUB_",
    "RUNNER_",
    "SWEEP_",
)


def _is_ci_provided(name: str) -> bool:
    return name in CI_PROVIDED_NAMES or name.startswith(CI_PROVIDED_PREFIXES)


def _declared_names(*mappings: Any) -> set[str]:
    """The names declared by any of the given ``env:`` mappings."""
    names: set[str] = set()
    for mapping in mappings:
        if isinstance(mapping, dict):
            names.update(str(key) for key in mapping)
    return names


def _referenced_names(script: str) -> set[str]:
    """The names the script reads."""
    names = set(_BRACED.findall(script))
    names.update(_BARE.findall(script))
    names.update(_ENVIRON.findall(script))
    return names


def _unresolved_names(script: str, declared: set[str]) -> set[str]:
    """The names the script reads that nothing gave it.

    **A name the script assigns is not unresolved**, even though the script
    also reads it: ``PY="${RELEASE_AUDIT_VENV}/bin/python"`` reads
    ``RELEASE_AUDIT_VENV`` and sets ``PY``, and ``PY`` is accounted for by
    the assignment on the line above.
    """
    assigned = set(_ASSIGNMENT.findall(script))
    return {
        name
        for name in _referenced_names(script)
        if name not in assigned and name not in declared and not _is_ci_provided(name)
    }


def _workflow_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / WORKFLOW_DIR).glob("*.yml"))


def _steps(document: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every ``(job name, step)`` pair in the workflow."""
    pairs: list[tuple[str, dict[str, Any]]] = []
    for job_name, job in (document.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict):
                pairs.append((str(job_name), step))
    return pairs


#: The workflows, named at collection time from this file's own location, so
#: the list does not depend on the working directory the run was started from.
WORKFLOW_NAMES: Final[tuple[str, ...]] = tuple(
    sorted(
        path.name
        for path in (Path(__file__).resolve().parent.parent / ".github" / "workflows").glob("*.yml")
    )
)


@pytest.mark.parametrize("workflow", WORKFLOW_NAMES)
def test_no_workflow_step_reads_a_variable_nothing_declared(repo_root: Path, workflow: str) -> None:
    """No step reads an environment variable that nothing gave it.

    The step's own ``env:``, the job's and the workflow's all count, and so
    does the platform's own set. Anything left over is a variable the step
    expects to find and will not.
    """
    path = repo_root / WORKFLOW_DIR / workflow
    assert path.is_file(), f"the workflow {workflow} is not there"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    workflow_env = _declared_names(document.get("env"))

    for job_name, step in _steps(document):
        script = step.get("run")
        if not isinstance(script, str):
            continue
        job = (document.get("jobs") or {}).get(job_name) or {}
        declared = _declared_names(step.get("env"), job.get("env")) | workflow_env
        unresolved = _unresolved_names(script, declared)
        assert not unresolved, (
            f"{workflow}, job {job_name}, step "
            f"{step.get('name', step.get('uses', '<unnamed>'))}: the script "
            f"reads {sorted(unresolved)}, and nothing declares them. A step "
            "that reads a variable nothing gave it does not say so; it fails "
            "later, somewhere else, naming something else."
        )


def test_the_checker_catches_a_step_that_was_given_nothing() -> None:
    """The checker must fail for the property, or it is not a witness.

    **This is the same shape as the mutation the release gate hit**: a step
    that reads a variable its ``env:`` does not declare. The checker is fed
    one here, and it has to name the variable -- otherwise it is a checker
    that passes everything, and passing everything is what it did.
    """
    script = 'cat "${SOME_REQUIREMENTS}"\n'
    assert _unresolved_names(script, set()) == {"SOME_REQUIREMENTS"}

    # And the same script with the declaration is not a finding.
    assert _unresolved_names(script, {"SOME_REQUIREMENTS"}) == set()

    # A variable the platform provides is not a finding either.
    assert _unresolved_names('echo "${RUNNER_TEMP}"\n', set()) == set()

    # A variable the script assigns is not a finding.
    assert _unresolved_names('PY="${AUDIT}/bin/python"\necho "${PY}"\n', {"AUDIT"}) == set()


def test_the_release_gate_names_its_requirements_file_in_both_steps(
    repo_root: Path,
) -> None:
    """The two steps that handle the requirements file must name it the same way.

    The general check above already refuses a step that reads a variable
    nothing declared. This one is here because the general check is a rule
    about *wiring*, and this is a rule about *the file*: the step that
    exports the closure and the step that audits it have to agree on where
    the export went, or the audit is about a different closure than the one
    the release will contain.

    A missing declaration in the auditing step is caught above; a
    declaration that points somewhere else is caught here.
    """
    path = repo_root / WORKFLOW_DIR / "release.yml"
    assert path.is_file(), "the release workflow is not there"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    naming_steps = []
    for job_name, step in _steps(document):
        script = step.get("run")
        if not isinstance(script, str):
            continue
        if "RELEASE_REQUIREMENTS" in script:
            declared = _declared_names(step.get("env"))
            naming_steps.append((job_name, step.get("name", "<unnamed>"), declared))

    assert naming_steps, (
        "the release workflow no longer mentions RELEASE_REQUIREMENTS, so the "
        "licence audit is not auditing the exported closure any more"
    )
    for job_name, step_name, declared in naming_steps:
        assert "RELEASE_REQUIREMENTS" in declared, (
            f"the release workflow's step {step_name!r} in job {job_name} "
            "mentions RELEASE_REQUIREMENTS but does not declare it"
        )


# ---------------------------------------------------------------------------
# The release gate's font list
# ---------------------------------------------------------------------------

#: The formats a font can arrive in.
#:
#: **This list is the test's own knowledge of the world, and it is
#: deliberately not read from the workflow.** A comparison between a list and
#: itself proves nothing: the workflow's list would define what "a font" means
#: and would then be found to agree with itself. This one says what a font
#: can be, and the workflow's list has to live inside it.
FONT_FORMATS: Final[frozenset[str]] = frozenset(
    {
        ".afm",
        ".bdf",
        ".dfont",
        ".eot",
        ".fnt",
        ".otc",
        ".otf",
        ".pcf",
        ".pfb",
        ".pfa",
        ".pfm",
        ".sfd",
        ".ttc",
        ".ttf",
        ".woff",
        ".woff2",
    }
)

#: The font licence audit, which names the fonts the wheels bundle.
FONT_AUDIT: Final[Path] = Path("docs") / "acceptance" / "LC-P1-14-font-licence-audit.md"

#: An inline code span in the audit -- how the audit names its files.
_BACKTICKED: Final[re.Pattern[str]] = re.compile(r"`([^`\n]+)`")

#: The extension of a named file.
_EXTENSION: Final[re.Pattern[str]] = re.compile(r"(\.[A-Za-z0-9]+)$")

#: A heredoc in a workflow step's script.
_HEREDOC: Final[re.Pattern[str]] = re.compile(r"<<'PY'\n(.*?)\nPY\n", re.DOTALL)


def _the_gate_program(repo_root: Path) -> str:
    """The Python the release gate runs to compare the artefacts' member lists.

    **The gate's own program, not a copy of it.** A test that re-implemented
    the check would be a test of the copy, and the copy would drift away from
    the gate exactly as the gate drifted away from the audit. So the program
    is read out of the workflow and run as it is written there.
    """
    document = yaml.safe_load(
        (repo_root / WORKFLOW_DIR / "release.yml").read_text(encoding="utf-8")
    )
    programs = [
        match.group(1)
        for _job_name, step in _steps(document)
        if isinstance(script := step.get("run"), str)
        for match in _HEREDOC.finditer(script)
        if "FONT_SUFFIXES" in match.group(1)
    ]
    assert len(programs) == 1, (
        "the release workflow does not hold exactly one member-list program with a "
        f"font list in it; found {len(programs)}"
    )
    return programs[0]


def _the_font_suffixes_the_gate_refuses(repo_root: Path) -> frozenset[str]:
    """The extensions the gate's own program refuses, read out of that program."""
    program = _the_gate_program(repo_root)
    for node in ast.walk(ast.parse(program)):
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if "FONT_SUFFIXES" not in names:
            continue
        assert isinstance(node.value, ast.Set), (
            "the release gate's FONT_SUFFIXES is not a set literal, so the list it "
            "refuses cannot be read out of it"
        )
        values: list[str] = []
        for element in node.value.elts:
            assert isinstance(element, ast.Constant) and isinstance(element.value, str), (
                "the release gate's FONT_SUFFIXES holds something that is not a string"
            )
            values.append(element.value)
        return frozenset(value.lower() for value in values)
    raise AssertionError("the release gate's program has no FONT_SUFFIXES in it")


def _the_fonts_the_audit_names(repo_root: Path) -> dict[str, str]:
    """The font files the licence audit names, by name, and the format of each."""
    text = (repo_root / FONT_AUDIT).read_text(encoding="utf-8")
    named: dict[str, str] = {}
    for span in _BACKTICKED.findall(text):
        extension = _EXTENSION.search(span)
        if extension is None:
            continue
        suffix = extension.group(1).lower()
        if suffix not in FONT_FORMATS:
            continue
        named[span] = suffix
    return named


def test_the_release_gate_refuses_every_font_the_licence_audit_names(repo_root: Path) -> None:
    """The gate's font list covers the fonts the licence audit names.

    **The audit names the fonts; the gate refuses them.** The audit counted
    reportlab's ``DarkGarden.sfd`` -- the source of the one bundled font that
    is not permissive -- and the gate that checks what a release contains did
    not know that extension, so the very file the audit names could have gone
    into a source distribution unnoticed.

    The two are compared, so neither can drift away from the other: a font the
    audit names that the gate would not refuse fails here, and a suffix in the
    gate that is not a font format fails here too.
    """
    named = _the_fonts_the_audit_names(repo_root)
    assert named, (
        "the font licence audit names no font file, so the comparison with the "
        "release gate's list would be vacuous"
    )

    refused = _the_font_suffixes_the_gate_refuses(repo_root)
    unrefused = {name: suffix for name, suffix in named.items() if suffix not in refused}
    assert not unrefused, (
        f"the release gate would not refuse these fonts the licence audit names: "
        f"{unrefused}. The audit names the file that is the font's source, and the "
        "gate has to know its extension."
    )

    not_a_font = sorted(refused - FONT_FORMATS)
    assert not not_a_font, (
        f"the release gate refuses suffixes that are not font formats: {not_a_font}. "
        "A list that grew to hold anything would stop being a list of fonts."
    )


def _git(root: Path, *arguments: str) -> None:
    """Run one git command in the tree, and insist that it worked."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"git {' '.join(arguments)} failed in {root} (exit {result.returncode}): "
        f"{result.stderr.strip()[-2000:]}"
    )


def _build_a_release_tree(root: Path, fonts: tuple[str, ...]) -> None:
    """A committed tree, a source distribution and a wheel, ready for the gate.

    Everything the gate's program compares is built here: the committed tree
    (a git repository with one commit), the source distribution (that tree
    plus the one file the build backend adds) and the wheel (the package's
    own files plus the six metadata files the release declares). A caller
    changes one thing -- the font files it plants -- and everything else stays
    a release the gate is meant to accept.
    """
    package = root / "src" / "labcairn"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""A package."""\n', encoding="utf-8")
    (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    (root / "NOTICE").write_text("A notice.\n", encoding="utf-8")

    planted: list[str] = []
    for name in fonts:
        path = root / "fonts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a font's bytes")
        planted.append(f"fonts/{name}")

    _git(root, "init", "--quiet")
    _git(root, "add", "--", "LICENSE", "NOTICE", "src/labcairn/__init__.py", *planted)
    _git(
        root,
        "-c",
        "user.name=LabCairn",
        "-c",
        "user.email=ci@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "a release tree",
    )

    members = ["LICENSE", "NOTICE", "src/labcairn/__init__.py", *planted]
    dist = root / "dist"
    dist.mkdir()
    with tarfile.open(dist / "labcairn-0.1.0.tar.gz", "w:gz") as archive:
        for member in members:
            archive.add(root / member, arcname=f"labcairn-0.1.0/{member}")
        info = tarfile.TarInfo("labcairn-0.1.0/PKG-INFO")
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))

    metadata = (
        "METADATA",
        "RECORD",
        "WHEEL",
        "entry_points.txt",
        "licenses/LICENSE",
        "licenses/NOTICE",
    )
    with zipfile.ZipFile(dist / "labcairn-0.1.0-py3-none-any.whl", "w") as archive:
        archive.writestr("labcairn/__init__.py", '"""A package."""\n')
        for name in metadata:
            archive.writestr(f"labcairn-0.1.0.dist-info/{name}", "")


def _run_the_gate(root: Path, program: str) -> subprocess.CompletedProcess[str]:
    """Run the gate's own member-list program over the tree at *root*."""
    script = root / "the-gate.py"
    script.write_text(program, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
    )


@pytest.mark.parametrize("font", ["DarkGarden.sfd", "Inter.woff2"])
def test_the_release_gate_refuses_a_source_distribution_that_carries_a_font(
    repo_root: Path,
    tmp_path: Path,
    font: str,
) -> None:
    """The gate's own program refuses a release that carries a font file.

    **The gate's program, run over a real distribution.** The bytes of a
    GPL v2 font, renamed to an extension the gate did not know, went into a
    source distribution and the gate exited zero. So the program is taken
    out of the workflow as it is written there, and it is run over a tree
    whose source distribution carries such a file -- and it has to refuse it
    and name the file.

    ``DarkGarden.sfd`` is the font's *source*, the very file the licence
    audit names; ``Inter.woff2`` is the format a browser ships. Both are
    fonts, and a gate that recognises only some of the formats is not a gate.
    """
    root = tmp_path / "tree"
    root.mkdir()
    _build_a_release_tree(root, (font,))

    result = _run_the_gate(root, _the_gate_program(repo_root))
    assert result.returncode != 0, (
        f"the release gate accepted a source distribution carrying {font!r} "
        f"(exit {result.returncode}).\n--- stdout ---\n{result.stdout[-4000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )
    assert "carries font files" in result.stdout, (
        f"the release gate refused the distribution but did not say it was a font:\n"
        f"--- stdout ---\n{result.stdout[-4000:]}"
    )
    assert font in result.stdout, (
        f"the release gate refused the distribution but did not name the font file "
        f"{font!r}:\n--- stdout ---\n{result.stdout[-4000:]}"
    )


def test_the_release_gate_accepts_a_release_that_carries_no_font(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    """The control: the same program, over a release that carries no font.

    A gate that refused everything would satisfy the test above, so it is
    asked about the release it is meant to accept, and it has to accept it.
    """
    root = tmp_path / "tree"
    root.mkdir()
    _build_a_release_tree(root, ())

    result = _run_the_gate(root, _the_gate_program(repo_root))
    assert result.returncode == 0, (
        f"the release gate refused a release that carries no font "
        f"(exit {result.returncode}).\n--- stdout ---\n{result.stdout[-4000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )


# ---------------------------------------------------------------------------
# The paid probe's own workflow
# ---------------------------------------------------------------------------

#: The workflow that discharges the protocol's fifth gate class, and its job.
PROVIDER_SMOKE_WORKFLOW: Final[str] = "provider-smoke.yml"
PROVIDER_SMOKE_JOB: Final[str] = "real-model-smoke"

#: The variables the live probe is configured by. A guard that checks three of
#: the four lets a run spend money against an endpoint nobody named.
PROBE_ENVIRONMENT: Final[tuple[str, ...]] = (
    "LABCAIRN_PROVIDER_SMOKE_KEY",
    "LABCAIRN_PROVIDER_SMOKE_MODEL",
    "LABCAIRN_PROVIDER_SMOKE_PROTOCOL",
    "LABCAIRN_PROVIDER_SMOKE_BASE_URL",
)

#: A guard line in the credential check: `[ -n "${NAME}" ] || missing+=(...)`.
_CREDENTIAL_GUARD: Final[re.Pattern[str]] = re.compile(r'\[\s*-n\s+"\$\{(\w+)\}"\s*\]')


def _smoke_document(repo_root: Path) -> Any:
    """The provider-smoke workflow, parsed.

    ``on:`` is YAML 1.1 boolean ``True``, so the trigger map is read under both
    keys — the same compromise the file's other readers make, and the reason
    this hands back an untyped mapping rather than a ``dict[str, Any]``.
    """
    text = (repo_root / WORKFLOW_DIR / PROVIDER_SMOKE_WORKFLOW).read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    assert isinstance(document, dict), f"{PROVIDER_SMOKE_WORKFLOW} is not a mapping"
    return document


def _smoke_triggers(document: Any) -> dict[str, Any]:
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), "the workflow declares no triggers"
    return triggers


def _smoke_step_script(document: Any, step_name: str) -> str:
    """The script of one named step, or a failure naming the steps that are there."""
    steps = ((document.get("jobs") or {}).get(PROVIDER_SMOKE_JOB) or {}).get("steps") or []
    for step in steps:
        if isinstance(step, dict) and step.get("name") == step_name:
            script = step.get("run")
            assert isinstance(script, str), (
                f"{PROVIDER_SMOKE_JOB}: step {step_name!r} has no script"
            )
            return script
    names = [
        str(step.get("name", step.get("uses", "<unnamed>")))
        for step in steps
        if isinstance(step, dict)
    ]
    raise AssertionError(f"{PROVIDER_SMOKE_JOB} has no step named {step_name!r}; it has {names}")


def _unguarded_probe_variables(script: str) -> set[str]:
    """Which probe variables this script does **not** refuse an empty value for."""
    guarded = set(_CREDENTIAL_GUARD.findall(script))
    return {name for name in PROBE_ENVIRONMENT if name not in guarded}


def _requires_the_probe_to_have_passed(script: str) -> bool:
    """Whether this script reads a report that distinguishes a skip from a pass.

    ``pytest`` exits 0 when every collected case skipped, so a workflow whose
    only signal is the exit code reports a paid probe that never ran as a
    success. Reading the JUnit document is what tells the two apart.
    """
    return "parse_junit" in script and '"passed"' in script and "SystemExit" in script


#: The three ways this job spells a path it writes to.
_WRITE_TARGETS: Final[tuple[str, ...]] = (
    "--junit-xml=",
    "LABCAIRN_PROVIDER_SMOKE_RECORD=",
    "cat ",
)


def _paths_written_inside_the_checkout(scripts: str) -> list[str]:
    """Every written path in these scripts that is not under the runner's temp."""
    offenders: list[str] = []
    for line in scripts.splitlines():
        stripped = line.strip()
        for target in _WRITE_TARGETS:
            if target not in stripped:
                continue
            remainder = stripped.split(target, 1)[1]
            value = remainder.split('"')[1] if '"' in remainder else remainder.split()[0]
            if not value.startswith("${RUNNER_TEMP}/"):
                offenders.append(value)
    return offenders


def _can_become_a_required_check(triggers: dict[str, Any]) -> bool:
    """Whether this workflow can be demanded of a pull request.

    A paid probe must not be. Branch protection cannot wait for a check that
    runs only where a secret exists, and amendment C-1 forbids rescuing that
    with a path filter, because a filtered required check is reported as
    `expected` and waits forever.
    """
    return "pull_request" in triggers or "push" in triggers


def test_the_provider_smoke_workflow_can_never_be_a_required_check(repo_root: Path) -> None:
    """The paid gate is dispatched and scheduled, and asked of nobody's PR.

    **The control:** adding a `push` trigger to the parsed triggers has to make
    the helper say it could be demanded, or the helper is a check that passes
    everything.
    """
    triggers = _smoke_triggers(_smoke_document(repo_root))
    assert "workflow_dispatch" in triggers, "the probe fires on a timer only, never on demand"
    assert "schedule" in triggers, "a paid probe nobody schedules rots as quietly as one never run"
    assert not _can_become_a_required_check(triggers), (
        f"{PROVIDER_SMOKE_WORKFLOW} triggers {sorted(triggers)}, so branch "
        "protection could wait on a job that runs only where a secret exists"
    )
    assert _can_become_a_required_check({**triggers, "push": {"branches": ["main"]}}), (
        "the trigger check cannot see a push trigger, so it cannot fail"
    )


def test_the_provider_smoke_workflow_refuses_loudly_without_a_credential(repo_root: Path) -> None:
    """Missing configuration is an error, never a skip that reports green.

    The witness in the suite skips when no credential is named, which is right
    for `uv run pytest` and wrong for a gate: a scheduled job whose single case
    skipped would print a pass. So the job refuses **before** spending, naming
    the variables that are empty and never their values.

    **The control:** the same script with one guard line removed has to be
    reported as unguarded, or this test is reading the file for atmosphere.
    """
    script = _smoke_step_script(
        _smoke_document(repo_root),
        "require a named credential and a declared model",
    )
    assert _unguarded_probe_variables(script) == set(), (
        f"the guard ignores {sorted(_unguarded_probe_variables(script))}; a run "
        "would spend money against an endpoint nobody named"
    )
    assert "exit 1" in script, "the guard finds a problem and continues anyway"

    doctored = "\n".join(
        line for line in script.splitlines() if 'LABCAIRN_PROVIDER_SMOKE_MODEL}"' not in line
    )
    assert _unguarded_probe_variables(doctored) == {"LABCAIRN_PROVIDER_SMOKE_MODEL"}, (
        "the guard check passed a script that had stopped checking the model"
    )


def test_the_provider_smoke_workflow_reads_the_report_not_the_exit_code(repo_root: Path) -> None:
    """A skipped probe is a failed gate, and the JUnit document is how it knows.

    **The control:** the bare pytest command — which is what this step would
    otherwise be — has to be reported as not requiring the probe to have run,
    because it does not: it trusts an exit code that says nothing about skips.
    """
    document = _smoke_document(repo_root)
    script = _smoke_step_script(document, "insist that the probe actually ran")
    assert _requires_the_probe_to_have_passed(script), (
        "the step does not read a report that distinguishes a skip from a pass"
    )
    assert "JUNIT_PATH" in script, "the report it reads is not the one pytest wrote"
    assert not _requires_the_probe_to_have_passed(
        "uv run pytest tests/test_real_provider_smoke.py -q\n"
    ), "the exit-code-only form would have satisfied this test, and that is the bug"


def test_the_probe_record_is_written_outside_the_checkout(repo_root: Path) -> None:
    """Every path this job writes goes to the runner's temp, not the tree.

    A file a run leaves in the checkout can be read back by a later step and
    presented as an artefact of the build, which is why every temp root in this
    repository lives outside the working tree -- CI included.

    **The control:** the same scripts with a report path spelled into the working
    directory have to be reported, or the check only passes by accident.
    """
    document = _smoke_document(repo_root)
    scripts = "\n".join(
        _smoke_step_script(document, name)
        for name in (
            "run the probe",
            "insist that the probe actually ran",
            "show what the endpoint answered",
        )
    )
    offenders = _paths_written_inside_the_checkout(scripts)
    assert not offenders, f"this job writes into the checkout: {offenders}"

    doctored = scripts.replace("${RUNNER_TEMP}/junit.xml", "junit.xml")
    assert _paths_written_inside_the_checkout(doctored) == ["junit.xml"], (
        "the path check passed a report written into the working tree"
    )


def test_the_workflow_avoids_the_context_github_refuses_to_parse(repo_root: Path) -> None:
    """A workflow file that cannot be parsed runs nothing, and says so only on dispatch.

    ``${{ runner.temp }}`` is not in the job-level ``env`` context. GitHub
    answers a workflow that uses it there with ``HTTP 422: failed to parse
    workflow`` at dispatch time -- measured, not reasoned: this file was written
    that way first, and the dispatch was refused before a single step existed.
    A workflow that never parses looks identical, from the repository's side, to
    a workflow that nobody dispatched.
    """
    text = (repo_root / WORKFLOW_DIR / PROVIDER_SMOKE_WORKFLOW).read_text(encoding="utf-8")
    document = _smoke_document(repo_root)
    jobs = document.get("jobs") or {}
    for job_name, job in jobs.items():
        env = (job or {}).get("env") or {}
        for name, value in env.items():
            assert "runner." not in str(value), (
                f"{PROVIDER_SMOKE_WORKFLOW}, job {job_name}, env {name}: the "
                "job-level env references the `runner` context, which GitHub "
                "will not parse — the paths under it are spelled in the steps"
            )
    assert "${RUNNER_TEMP}" in text, (
        "nothing writes to the runner's temp, so this job's scratch is somewhere else"
    )


# ---------------------------------------------------------------------------
# NOTICE §2.2/§2.3 against the closure the release gate audits.
#
# `scripts/notice_licence_watch.py` is loaded the way `test_ci_shard_coverage.py`
# loads `scripts/outsider_path.py`: the script is the tool, the tool is run rather
# than paraphrased, and `sys.modules` is populated first because the script uses
# dataclasses and `dataclasses` looks the defining module up by name.
# ---------------------------------------------------------------------------

#: The reader, loaded once per run. `uv export` takes a fraction of a second and
#: several cases need the same closure, so it is cached rather than re-run.
_LICENCE_WATCH: dict[str, Any] = {}


def _licence_watch() -> Any:
    """`scripts/notice_licence_watch.py`, loaded the way the tool is run."""
    if "module" not in _LICENCE_WATCH:
        script = Path(__file__).resolve().parent.parent / "scripts" / "notice_licence_watch.py"
        spec = importlib.util.spec_from_file_location(
            "notice_licence_watch_for_release_witness", script
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _LICENCE_WATCH["module"] = module
    return _LICENCE_WATCH["module"]


def _closure_read() -> Any:
    """The closure, read once: `uv export --frozen --no-dev` over this tree's lock."""
    if "closure" not in _LICENCE_WATCH:
        watch = _licence_watch()
        _LICENCE_WATCH["closure"] = watch.read_closure(watch.export_requirements())
    return _LICENCE_WATCH["closure"]


def test_notice_closure_figures_are_the_figures_the_lock_markers_produce(repo_root: Path) -> None:
    """§2.2's five closure figures are recomputed from the markers the lock records.

    **The property.** §2.2 states 171 requirement lines, 167 on Linux, 165 on macOS,
    168 on Windows and a union of 170, and explains the differences as the
    platform-conditional packages. Those five numbers are not a measurement that has
    to be carried forward by hand: they are what `packaging.markers` answers for the
    markers ``uv export`` prints for this lock, and the same evaluator the release
    gate's own audit uses.

    **Why it needed a witness.** A dependency arriving with a Windows marker, or a
    marker being narrowed, changes all five figures at once. §2.2 would have kept
    printing 171/167/165/168/170 and every other check would have stayed green,
    because nothing read the lock's markers against the section's prose.

    **The union is not the line count.** The export resolves 171 ``name==version``
    lines; the union of what the three supported platforms install is 170, because one
    distribution carries ``sys_platform == 'emscripten'`` and installs on none of
    them. A reader that took §2.2's "union is 170" as the line count would have
    reported a real, correct section as wrong -- which is a red about the witness, not
    about the record.
    """
    watch = _licence_watch()
    read = _closure_read()
    recorded = watch.closure_counts(watch.read_notice())

    assert len(read.rows) == 171, (
        f"the export names {len(read.rows)} requirement lines; §2.2 states 171, and the "
        "figure this test is about has stopped being the one the lock gives"
    )
    problems = watch.closure_count_problems(read, recorded)
    assert not problems, f"§2.2's closure figures disagree with the lock's own markers: {problems}"

    # The control: the same reader over an export with one Windows-conditional
    # package removed. §2.2's figures must move, and the Windows count must move with
    # it, or the comparison is not reading the markers.
    mutated_export = "\n".join(
        line
        for line in watch.export_requirements(repo_root=repo_root).splitlines()
        if not line.startswith("pywin32==")
    )
    assert mutated_export.count("pywin32==") == 0, "the control did not remove the pinned row"
    mutated = watch.closure_count_problems(watch.read_closure(mutated_export), recorded)
    assert any("windows" in problem for problem in mutated), (
        f"removing a Windows-pinned package left §2.2's Windows figure satisfied: {mutated}"
    )
    assert any("total" in problem for problem in mutated), (
        f"removing a pinned package left §2.2's total satisfied: {mutated}"
    )

    # And the reverse control: a §2.2 whose figure has drifted reddens it.
    drifted = dict(recorded)
    drifted["total"] = recorded["total"] + 1
    drift_problems = watch.closure_count_problems(read, drifted)
    assert len(drift_problems) == 1 and "total" in drift_problems[0], (
        f"a §2.2 total off by one produced: {drift_problems}"
    )


def test_notice_licence_census_closes_against_the_installed_closure(repo_root: Path) -> None:
    """§2.2's census rows are the labels the installed distributions carry.

    **What is compared.** The labels come from the release gate's own ``label_for``
    function -- extracted from ``release.yml``'s licence-audit heredoc, not rewritten
    here -- applied to every pinned distribution installed in the environment running
    this. §2.2's sixteen rows are then checked against them: a row smaller than what
    is installed, and a label §2.2 names no row for, are both findings.

    **Where the limit is stated rather than hidden.** Three pinned packages -- jeepney,
    secretstorage (Linux-only) and httpx2-jsfetch (emscripten-only) -- have nothing
    installed on the platform running this, so they contribute no label. The total is
    therefore closed as *rows = labels answered here + foreign packages*, and the
    foreign set is exactly the one §2.2 itself explains. When a package §2.2 counts has
    nothing readable installed -- a damaged venv, not a licence question -- the total is
    reported as **not run** instead of being closed against a number that includes the
    damage. A red that blames NOTICE for a broken environment is the failure this split
    exists to prevent, and the control below exercises both states.
    """
    watch = _licence_watch()
    read = _closure_read()
    notice_text = watch.read_notice()
    recorded = watch.census_rows(notice_text)
    installed = watch.installed_versions(read.distinct_rows)
    labels = watch.label_installed(read.distinct_rows)
    foreign, broken = watch.answerability(read, installed)

    assert recorded, "§2.2 prints no census rows to compare"
    assert labels, (
        "no installed distribution answered with a licence label, so the census "
        "is not a measurement"
    )
    assert not broken, (
        f"the environment cannot answer {len(broken)} pinned package(s) §2.2 counts for "
        f"this platform: {', '.join(sorted(row.name for row in broken))}. The licence census "
        "cannot be measured in this environment; fix the environment rather than the record."
    )

    problems = watch.census_problems(recorded, labels, foreign, broken)
    assert not problems, f"§2.2's census does not close against the installed closure: {problems}"

    # The controls, on fixtures: the same comparison function, with one value changed
    # each time.
    busiest_label = max(labels.values(), key=lambda entry: recorded.get(entry[0], 0))[0]
    too_small = dict(recorded)
    too_small[busiest_label] = 1
    small_problems = watch.census_problems(too_small, labels, foreign)
    assert any(busiest_label in problem and "records 1" in problem for problem in small_problems), (
        f"a census row cut to 1 for {busiest_label!r} was not reported: {small_problems}"
    )

    # A §2.2 row for a licence nothing in the closure carries. The arm that catches it
    # is the total, not the per-row loop: the per-row loop walks the labels the
    # installed distributions actually carry, so a label with no carrier never enters
    # it -- and it could not, because a row whose only carriers are the three packages
    # this platform does not install looks identical to a row nothing carries. Naming
    # the row would require knowing each foreign package's label, which is the part
    # there is no artefact for here.
    invented = dict(recorded)
    invented["GPL-3.0-only"] = 1
    invented_problems = watch.census_problems(invented, labels, foreign, broken)
    assert any("census rows add to 172" in problem for problem in invented_problems), (
        f"a §2.2 row for a licence nothing carries left the census total closed: "
        f"{invented_problems}"
    )

    # A dependency leaving the closure while §2.2 keeps its row: no individual row is
    # too small, so only the total notices. This is why the total is checked at all.
    dropped_label = next(label for label, _source in labels.values() if recorded.get(label, 0) >= 2)
    thinned = {key: value for key, value in labels.items() if value[0] != dropped_label}
    assert len(thinned) < len(labels), "the control removed nothing"
    total_problems = watch.census_problems(recorded, thinned, foreign)
    assert any("census rows add to" in problem for problem in total_problems), (
        f"removing every carrier of {dropped_label!r} did not redden the census "
        f"total: {total_problems}"
    )

    # The damaged-environment state, asserted rather than left to the real tree: when
    # something this platform should have installed is missing, the total arm must say
    # it did not run, and must not accuse the record.
    broken_rows = [read.distinct_rows[0]]
    broken_problems = watch.census_problems(recorded, labels, foreign, broken_rows)
    assert any("could not be closed" in problem for problem in broken_problems), (
        f"an unanswerable package did not put the census total into its not-run "
        f"state: {broken_problems}"
    )
    assert not any(
        "no longer accounts for its own total" in problem for problem in broken_problems
    ), f"a damaged environment was reported as a record that went stale: {broken_problems}"


def test_notice_census_row_count_is_the_rows_it_prints() -> None:
    """§2.2 states how many distinct licence results it prints, and prints that many.

    The section says "the sixteen distinct results were" and then prints rows. That is
    a claim about its own table, and a table edited without editing the sentence -- or
    a sentence left behind when a licence identifier leaves the closure -- is the small,
    ordinary drift a record suffers. It costs nothing to check and it is the kind of
    drift that makes a reader stop trusting the rest of the section.

    **The control:** the same reader over a copy of the sentence with the count changed.
    """
    watch = _licence_watch()
    notice_text = watch.read_notice()
    recorded = watch.census_rows(notice_text)
    claimed = watch.census_row_count_claim(notice_text)

    assert claimed is not None, "§2.2 states no count of distinct licence results"
    problems = watch.census_row_count_problems(recorded, claimed)
    assert not problems, f"§2.2's row-count sentence and its rows disagree: {problems}"

    drifted = watch.census_row_count_problems(recorded, claimed + 1)
    assert len(drifted) == 1, f"a row count stated one too high produced: {drifted}"

    # And the other direction: a row removed from the table is caught, not resized.
    without_one = dict(recorded)
    without_one.pop(next(iter(without_one)))
    removed_problems = watch.census_row_count_problems(without_one, claimed)
    assert len(removed_problems) == 1, (
        f"§2.2 printing one row fewer than it claims produced: {removed_problems}"
    )


def test_notice_bundled_licence_files_state_the_clauses_named_for_them(tmp_path: Path) -> None:
    """§2.3's four bundled-licence entries are checked against the licence files.

    **What §2.3 claims, and what is checked.** The section does not say "these packages
    have licence files". It names a file inside an installed distribution and states
    which licence that file carries -- "its licence file
    (`numpy-2.5.4.dist-info/licenses/LICENSE.txt`) carries the GCC Runtime Library
    Exception 3.1 for the OpenBLAS build … stated as GPL-3.0-or-later WITH
    GCC-exception-3.1", "an LGPL notice for the bundled adodbapi module
    (`pywin32-312.dist-info/licenses/adodbapi/license.txt`)", "the Scintilla licence for
    the bundled Scintilla sources". So the check opens the file §2.3 names and looks for
    the clause §2.3 credits it with. A file-exists-only check would pass a tree where
    the LGPL notice had been replaced by a different licence in the same path.

    **Claims are paired with paths in document order.** A bullet naming one file claims
    everything else it says about that file, which is what makes numpy's entry
    checkable at all: its clauses are stated *after* the path, and a pairing that
    stopped at the path would check nothing and pass vacuously. A bullet naming two files
    (pywin32) is the reason the window is not simply extended for everyone -- there the
    text between the paths belongs to the first path, and extending the last window
    backwards would credit the Scintilla licence with the LGPL clause.

    **The installed version is part of the claim.** A licence file is evidence only about
    the artefact it belongs to, so `pywin32 312` against an installed `pywin32 313` is
    reported: the file at that path may be a different file.
    """
    watch = _licence_watch()
    notice_text = watch.read_notice()
    entries = watch.bundled_entries(notice_text)
    assert len(entries) == 4, f"§2.3 names {len(entries)} entries; the section names four"
    # Three of the four name a licence file inside an installed distribution. The
    # certifi/tqdm entry names none, and that is §2.3 being accurate rather than
    # incomplete: its claim is about each package's own licence, and the section says
    # outright that "LabCairn does not redistribute either of them". An assertion that
    # all four carry a path would demand a file §2.3 correctly does not cite.
    with_paths = [entry for entry in entries if entry.claims]
    assert len(with_paths) == 3, (
        f"§2.3 entries naming a licence path: {len(with_paths)}; the numpy, Pillow and "
        f"pywin32 entries each name at least one, and the paths read out of them are "
        f"{[claim.path for entry in with_paths for claim in entry.claims]}"
    )
    assert sum(len(entry.claims) for entry in with_paths) == 4, (
        f"§2.3's licence paths read out of the three entries: "
        f"{[claim.path for entry in with_paths for claim in entry.claims]}"
    )

    site = watch.site_packages_of()
    read = _closure_read()
    installed = watch.installed_versions(read.distinct_rows)
    foreign_rows, _broken = watch.answerability(read, installed)
    problems, unanswerable, foreign_claims = watch.bundled_entry_problems(
        entries, site, [row.name for row in foreign_rows]
    )
    assert not unanswerable, (
        f"§2.3's licence paths could not be checked: {unanswerable} sit in a dist-info "
        "that cannot be read here. This is the environment, not the record."
    )
    assert not problems, (
        f"§2.3's bundled-licence claims do not match the installed files: {problems} "
        f"(claims this platform does not install and so cannot check: {foreign_claims})"
    )

    version_problems = watch.installed_version_problems(
        entries, watch.installed_versions(_closure_read().distinct_rows)
    )
    assert not version_problems, (
        f"§2.3 describes versions this tree does not resolve: {version_problems}"
    )

    # The controls, on a synthetic site-packages tree: the same function, with the
    # evidence changed under it. Each state the function distinguishes is put to it.
    dist_info = "synth-1.0.0.dist-info"
    licence_relative = f"{dist_info}/licenses/LICENSE.txt"

    claims = watch.PathClaim(path=licence_relative, claims=("lgpl",))
    entry = watch.BundledEntry(
        opening="synth 1.0.0 — its licence directory carries an LGPL notice",
        package="synth",
        version="1.0.0",
        claims=(claims,),
        text="* synth 1.0.0 — its licence directory carries an LGPL notice",
        folded="* synth 1.0.0 — its licence directory carries an LGPL notice",
    )

    def build(root: Path, licence_text: str) -> Path:
        """A site-packages directory holding one readable dist-info with a licence."""
        info = root / dist_info
        licences = info / "licenses"
        licences.mkdir(parents=True)
        (info / "METADATA").write_text("Name: synth\nVersion: 1.0.0\n", encoding="utf-8")
        (licences / "LICENSE.txt").write_text(licence_text, encoding="utf-8")
        return root

    # (a) The file is there and states the clause §2.3 credits it with: clean. This is
    # the state the real tree is in, restated on a fixture so the three states below
    # are distinguishable from it rather than inferred from its absence.
    stating = build(tmp_path / "stating", "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1\n")
    clean_problems, clean_unanswerable, clean_foreign = watch.bundled_entry_problems(
        [entry], stating
    )
    assert clean_problems == [] and clean_unanswerable == [], (
        f"the clean fixture did not compare clean: {clean_problems} / {clean_unanswerable}"
    )
    assert clean_foreign == [], (
        f"the clean fixture excused a claim it should have checked: {clean_foreign}"
    )

    # (b) The file is there but states a different licence. This is the finding a
    # file-exists-only check misses: the path §2.3 names is still exactly right.
    swapped = build(
        tmp_path / "swapped", "MIT License\n\nPermission is hereby granted, free of charge\n"
    )
    swapped_problems, swapped_unanswerable, swapped_foreign = watch.bundled_entry_problems(
        [entry], swapped
    )
    assert len(swapped_problems) == 1 and "lgpl" in swapped_problems[0], (
        f"an LGPL claim over a file holding MIT text produced: {swapped_problems}"
    )
    assert swapped_unanswerable == [], (
        f"the swapped case was reported as unanswerable: {swapped_unanswerable}"
    )
    assert swapped_foreign == [], (
        f"the swapped case excused a claim it should have checked: {swapped_foreign}"
    )

    # (c) The distribution is installed but its dist-info cannot be read -- no METADATA,
    # which is what a damaged installation looks like. NOT a finding about NOTICE: the
    # arm did not run, and that is what has to be reported.
    hollow_root = tmp_path / "hollow"
    hollow_info = hollow_root / dist_info
    (hollow_info / "licenses").mkdir(parents=True)
    hollow_problems, hollow_unanswerable, hollow_foreign = watch.bundled_entry_problems(
        [entry], hollow_root
    )
    assert hollow_problems == [], (
        f"a dist-info with no METADATA was reported as a §2.3 failure: {hollow_problems}"
    )
    assert hollow_unanswerable == [licence_relative], (
        f"the unreadable dist-info was not reported as the arm not running: {hollow_unanswerable}"
    )
    assert hollow_foreign == [], (
        f"the unreadable dist-info was excused as platform-foreign: {hollow_foreign}"
    )

    # (d) The distribution is not installed at all: a finding about NOTICE, because §2.3
    # names a path inside a distribution this closure does not hold.
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    missing_problems, missing_unanswerable, missing_foreign = watch.bundled_entry_problems(
        [entry], missing_root
    )
    assert len(missing_problems) == 1 and "no distribution named" in missing_problems[0], (
        f"§2.3 naming a path inside an uninstalled distribution produced: {missing_problems}"
    )
    assert missing_unanswerable == [], (
        f"an absent distribution was reported as unreadable: {missing_unanswerable}"
    )
    assert missing_foreign == [], (
        f"an absent distribution this platform installs was excused: {missing_foreign}"
    )

    # (d2) The same absent distribution, but one this platform does not install:
    # the claim is not checkable here, and it is not a finding about NOTICE.
    foreign_problems, foreign_unanswerable, foreign_claims = watch.bundled_entry_problems(
        [entry], missing_root, ["synth"]
    )
    assert foreign_problems == [], (
        f"a claim inside a distribution this platform does not install was reported as a "
        f"finding about NOTICE: {foreign_problems}"
    )
    assert foreign_unanswerable == [], (
        f"a platform-foreign claim was reported as unreadable: {foreign_unanswerable}"
    )
    assert len(foreign_claims) == 1 and "not installed on this platform" in foreign_claims[0], (
        f"the platform-foreign claim was not reported as such: {foreign_claims}"
    )

    # (e) The version §2.3 names is part of the claim, on a fixture where it disagrees.
    stale = watch.BundledEntry(
        opening="synth 1.0.0 — its licence file",
        package="synth",
        version="1.0.0",
        claims=(claims,),
        text="* synth 1.0.0 — its licence file",
        folded="* synth 1.0.0 — its licence file",
    )
    stale_problems = watch.installed_version_problems([stale], {"synth": "2.0.0"})
    assert len(stale_problems) == 1 and "2.0.0" in stale_problems[0], (
        f"§2.3 describing synth 1.0.0 against an installed 2.0.0 produced: {stale_problems}"
    )
    matching_problems = watch.installed_version_problems([stale], {"synth": "1.0.0"})
    assert matching_problems == [], (
        f"matching versions were reported as a mismatch: {matching_problems}"
    )


def test_notice_conditional_packages_are_the_packages_the_release_gate_allows() -> None:
    """§2.3's conditional-licence packages and the gate's allow-list are the same list.

    **Two artefacts, neither of them NOTICE.** The gate's ``CONDITIONAL`` map comes out
    of ``release.yml``'s own text; §2.3's packages come out of §2.3's own prose. The
    gate is what decides whether a release may ship a package under a conditional
    licence, and §2.3 is the record of which packages carry one. If they disagree,
    either the release ships something §2.3 never recorded, or §2.3 records a condition
    the gate would refuse -- and both of those are the release gate and the notice
    telling different stories about the same closure.

    **The gate's refusal is also shown to be reachable.** The map's allowed set is
    checked against installed labels: an installed distribution carrying a conditional
    licence the gate records no allowance for is reported, which is what makes the map
    a live check rather than a comment.

    **The controls:** the same comparison over a §2.3 with the MPL entry removed, and
    over one that names a package the gate does not allow.
    """
    watch = _licence_watch()
    notice_text = watch.read_notice()
    entries = watch.bundled_entries(notice_text)
    read = _closure_read()
    labels = watch.label_installed(read.distinct_rows)

    problems = watch.conditional_crosscheck_problems(entries, labels)
    assert not problems, (
        f"§2.3's conditional entries and the release gate's CONDITIONAL map disagree: {problems}"
    )

    # The gate's map is not vacuous: it must allow something §2.3 records, and the
    # installed closure must actually carry the licence the gate allows for those names.
    conditional = watch.release_audit_namespace()["CONDITIONAL"]
    assert conditional, (
        "the release audit defines no CONDITIONAL map, so the comparison below is vacuous"
    )
    carried = {
        label
        for _name, (label, _source) in labels.items()
        if any(licence in label for licence in conditional)
    }
    assert carried & set(conditional), (
        f"no installed distribution carries any licence the gate treats as conditional "
        f"({sorted(conditional)}), so §2.3's conditional list is unchecked here"
    )

    # (a) §2.3 with its MPL entry deleted: the gate allows certifi and tqdm under
    # MPL-2.0, and the record no longer says so.
    without_mpl = "\n".join(
        line for line in notice_text.split("\n") if not line.startswith("  * MPL-2.0 — certifi")
    )
    assert "MPL-2.0 — certifi" not in without_mpl, "the control did not change §2.3"
    removed_problems = watch.conditional_crosscheck_problems(
        watch.bundled_entries(without_mpl), labels
    )
    assert any("certifi" in problem for problem in removed_problems), (
        f"a §2.3 that stopped recording certifi under MPL-2.0 produced: {removed_problems}"
    )
    assert any("tqdm" in problem for problem in removed_problems), (
        f"a §2.3 that stopped recording tqdm under MPL-2.0 produced: {removed_problems}"
    )

    # (b) §2.3 naming a package under a conditional licence the gate does not allow.
    invented = notice_text.replace(
        "  * MPL-2.0 — certifi (MPL-2.0) and tqdm (MPL-2.0 AND MIT, so MIT is",
        "  * MPL-2.0 — certifi (MPL-2.0) and not-a-real-package (MPL-2.0) and "
        "tqdm (MPL-2.0 AND MIT, so MIT is",
        1,
    )
    assert "not-a-real-package (MPL-2.0)" in invented, "the control did not change §2.3"
    pinned = {watch.canonical(row.name): row.version for row in read.distinct_rows}
    invented_problems = watch.package_terms_problems(
        watch.bundled_entries(invented), labels, pinned
    )
    assert any("not-a-real-package" in problem for problem in invented_problems), (
        f"§2.3 naming a package the closure does not pin produced: {invented_problems}"
    )


def test_the_licence_reader_that_reads_nothing_is_not_a_green_witness() -> None:
    """Each reader arm refuses to answer when it has nothing to read.

    **Why this case exists.** Every case above is satisfied by an empty list of
    problems. A reader that collected nothing -- an export that parsed no rows, a §2.2
    whose census rows the pattern did not match, a §2.3 whose bullets were not bullets
    -- would produce an empty list and make all of them green at once. That is this
    repository's recurring failure, so each arm is put to the input that should stop it
    and required to stop.

    **And the audit-selection guard is exercised.** ``release.yml`` carries two Python
    heredocs and only one is the licence audit; taking the first runs the release
    member-list step, which dies on the absence of a build. The reader selects the audit
    by the function it defines, and this case asserts exactly one block qualifies rather
    than trusting that the workflow keeps its heredocs in a pleasing order.
    """
    watch = _licence_watch()

    # Annotated rather than left to inference: a tuple of heterogeneous lambdas whose
    # return types differ is inferred as an untyped callable, and strict mypy refuses to
    # call one. The return value is not what this loop uses -- only whether the call
    # raises -- so `object` is the honest type.
    refusals: tuple[tuple[str, Callable[[], object]], ...] = (
        (
            "export rows with no requirements",
            lambda: watch.read_export_rows("lockfileVersion: 1\n"),
        ),
        (
            "§2.2 with no census rows",
            lambda: watch.census_rows("2.2  The whole closure\n---\nno table here\n2.3  Next\n"),
        ),
        (
            "§2.2 with a missing figure",
            lambda: watch.closure_counts(
                "2.2  The whole closure\n---\nresolves 171 requirement lines\n2.3  Next\n"
            ),
        ),
        (
            "§2.3 with no bullets",
            lambda: watch.bundled_entries(
                "2.3  The three that carry a condition\n---\nprose only\n3.  Next\n"
            ),
        ),
        ("a missing subsection", lambda: watch.census_rows("1.  Something\n---\nnothing here\n")),
    )

    for name, call in refusals:
        try:
            call()
        except (RuntimeError, ValueError):
            continue
        raise AssertionError(f"{name} produced an answer where it should have refused")

    # The reader's own refusal is what makes "no problems" mean something: assert that
    # the arms which did run actually read something out of the real tree.
    read = _closure_read()
    assert len(read.rows) > 100, f"the export read {len(read.rows)} rows from this lock"
    assert len(watch.census_rows(watch.read_notice())) > 10, "§2.2's census read nothing"
    assert len(watch.bundled_entries(watch.read_notice())) == 4, "§2.3's entries read nothing"
    assert watch.installed_versions(read.distinct_rows), (
        "no installed distribution was found to compare with"
    )

    workflow = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")
    blocks = re.findall(r"<<'PY'\n(.*?)\n {10}PY\n", workflow, re.S)
    audits = [block for block in blocks if "def label_for" in block]
    assert len(audits) == 1, (
        f"{len(audits)} heredocs in release.yml define label_for; the licence audit is "
        "expected to be exactly one, and a reader that picked one of them by position "
        "would run the wrong program"
    )


# ---------------------------------------------------------------------------
# NOTICE §2.5.1's LGPL delivery record.
#
# `scripts/lgpl_source_release.py` is loaded the way the other scripts in this
# file are: the script is the tool, the tool is run rather than paraphrased, and a
# witness that re-derived its patterns would be a second copy that can drift from
# the thing a release actually runs.
# ---------------------------------------------------------------------------


_LGPL_DELIVERY: dict[str, Any] = {}

#: The files §2.5.1's delivery entries tell a release to carry. Named here so the
#: checklist case can require each step line to carry one, rather than accepting a
#: name that only appears in a neighbouring detail line.
STEP_NAMES: Final[tuple[str, ...]] = (
    "StdUtils.2018-10-27.Sources.tar",
    "Nsis7z_19.00.7z",
    "7z1900-src.7z",
)


def _lgpl_delivery() -> Any:
    """`scripts/lgpl_source_release.py`, loaded the way the tool is run."""
    if "module" not in _LGPL_DELIVERY:
        script = Path(__file__).resolve().parent.parent / "scripts" / "lgpl_source_release.py"
        spec = importlib.util.spec_from_file_location("lgpl_source_release_for_witness", script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _LGPL_DELIVERY["module"] = module
    return _LGPL_DELIVERY["module"]


def _lgpl_script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts" / "lgpl_source_release.py"


def _notice_text() -> str:
    return (Path(__file__).resolve().parent.parent / "NOTICE").read_text(encoding="utf-8")


def _env_directory(name: str) -> Path | None:
    """A directory an environment variable names, or None where it names none that exists."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    return candidate if candidate.is_dir() else None


def _drop_delivery_label(notice_text: str, binary: str, label: str) -> str:
    """The record with one label of one delivery entry removed, as a control."""
    heading = f"    Delivery entry — `{binary}`"
    start = notice_text.index(heading)
    end = notice_text.index("\n\n", start)
    block = notice_text[start:end]
    kept: list[str] = []
    dropping = False
    for line in block.split("\n"):
        match = re.match(r"^ {6}([a-z]+) +\S", line)
        if match and match.group(1) == label:
            dropping = True
            continue
        if dropping and re.match(r"^ {7,}\S", line):
            continue
        dropping = False
        kept.append(line)
    assert "\n".join(kept) != block, f"the control removed nothing from the {binary} entry"
    return notice_text[:start] + "\n".join(kept) + notice_text[end:]


def test_the_delivery_checklist_runs_as_a_command_and_reads_the_record() -> None:
    """The tool a release would run runs here, over the real record, and says what it read.

    **Why the command and not only the import.** A witness that only imports a
    script shows that its functions work when called from Python. A release
    performs the script as a command, and the two can disagree: the CLI can render
    nothing while every function returns a list, and a checklist that prints no
    step is a checklist nobody carries into the release. So the CLI is run, its
    exit code read from the process and not from a pipe, and its output required to
    name both binaries, both of the `nsis7z.dll` artefacts, and the record's own
    state.
    """
    # The child prints §-bearing text, and a console encoding other than UTF-8
    # arrives as replacement characters: a reader that then asserted on "§2.5.1"
    # would go red over the encoding rather than over the record. The project's
    # other subprocess cases pin PYTHONIOENCODING for the same reason.
    completed = subprocess.run(
        [sys.executable, str(_lgpl_script_path())],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert completed.returncode == 0, (
        f"scripts/lgpl_source_release.py exited {completed.returncode}: {completed.stderr.strip()}"
    )
    out = completed.stdout
    for expected in (
        "StdUtils.2018-10-27.Sources.tar",
        "Nsis7z_19.00.7z",
        "7z1900-src.7z",
        "PARTLY DONE",
        "LGPL",
    ):
        assert expected in out, f"the checklist printed no {expected!r}:\n{out}"
    assert "carry" in out, f"the checklist named no step to perform:\n{out}"
    # Each carry line names the file itself. A checklist whose steps say `carry` and
    # leave the name to a neighbouring line is not a checklist a release can act on
    # line by line, and an assertion that only looked for the names anywhere in the
    # output would be satisfied by the detail lines while the step line said nothing.
    steps = [line for line in out.splitlines() if line.lstrip().startswith("carry")]
    assert len(steps) >= 3, f"the checklist printed {len(steps)} carry line(s):\n{out}"
    for step in steps:
        assert any(name in step for name in STEP_NAMES), (
            f"a carry line named no file to carry: {step!r}\n{out}"
        )
    # The record's own state, echoed rather than restated by the script.
    assert "§2.5.1 states the obligation as" in out, (
        f"the checklist asserted a state instead of quoting §2.5.1's:\n{out}"
    )


def test_every_lgpl_binary_notice_records_has_a_delivery_entry() -> None:
    """Each §2.5 binary under an LGPL term has a §2.5.1 entry, and each entry is complete.

    **The property.** LGPL-2.1 §4 obliges a distributor to convey the complete
    corresponding machine-readable source with the object code, and §2.5.1 records
    how this distribution means to do it: for each LGPL binary, a delivery entry
    naming the file a release carries, its byte count, its sha256, the URL the bytes
    come from, and the point at which it is offered. A record that names a source in
    prose -- "the corresponding source is now located" -- is a record a release
    cannot perform, and it is the shape this section had before it was rewritten.

    **Why the record is what is watched.** Nothing has been released, so no artefact
    exists to compare the record with. That makes the record the whole of the
    obligation as it stands, and it makes an incomplete entry invisible until the
    release that needs it. Each entry is therefore asserted field by field -- file,
    byte count, 64-hex-digit sha256, URL, timing -- rather than by counting entries,
    because an entry with a name and a URL but no hash is exactly as unperformable
    as no entry at all.

    **What this does not claim.** It does not say the obligation is discharged, and
    it does not say §2.5.1's reading of "corresponding source" is the correct one:
    §2.5.1 states both readings and puts the choice to the owner. What is watched is
    that whichever reading is adopted, the record states a step.
    """
    watch = _lgpl_delivery()
    notice_text = _notice_text()
    records = watch.binary_records(notice_text)
    entries = watch.delivery_entries(notice_text)
    state = watch.obligation_state(notice_text)

    lgpl = [record for record in records if record.is_lgpl]
    assert lgpl, "§2.5 records no binary under an LGPL term, so the delivery record watches nothing"
    assert {record.name for record in lgpl} == {"StdUtils.dll", "nsis7z.dll"}, (
        f"§2.5 records these binaries under an LGPL term: {[record.name for record in lgpl]}; "
        "the delivery record is written for two, and a third arriving means §2.5.1 has to "
        "say what its corresponding source is"
    )

    problems = watch.coverage_problems(records, entries)
    assert problems == [], f"§2.5.1's delivery record is incomplete: {problems}"

    assert state.startswith("PARTLY DONE"), (
        f"§2.5.1 states the corresponding-source obligation as {state!r}; every entry below "
        "is written as a step a future release performs, so a record that moved off PARTLY "
        "DONE has to say what it moved to"
    )

    for entry in entries:
        assert entry.artefact_name(), f"{entry.label}: the entry names no artefact"
        assert entry.recorded_sha256(), f"{entry.label}: the entry records no sha256"
        assert entry.recorded_bytes(), f"{entry.label}: the entry records no byte count"
        assert re.search(r"https?://", " ".join(entry.labels.values())), (
            f"{entry.label}: the entry names no upstream URL"
        )

    # **The name a release carries is a name the record itself knows.** An artefact name
    # that appears nowhere outside its own `artefact` label is a name nothing cross-checks:
    # renaming it -- the sha256 shape still legal, the byte count untouched -- left R3 and
    # the checks above green, because no assertion asked where the name comes from. So each
    # name must resolve inside the record: it is either a file §5.4's fetch list names (the
    # two `nsis7z.dll` archives, fetched by name), or it is the tar the `StdUtils.dll`
    # entry derives from the fetched `sources.tbz2` -- the record's own sentence says the
    # bunzip2 output is byte-identical to the artefact, and §5.4's cross-check line pins
    # the bytes by printing the artefact's sha256. Both readings are internal to NOTICE,
    # so this arm runs in CI without any upstream archive on the machine.
    section_54 = watch._subsection(notice_text, "5.4")
    fetched_names = set(re.findall(r"-o ([A-Za-z0-9._-]+) ", section_54))

    def _stem(name: str) -> str:
        return name.rsplit(".", 1)[0].lower()

    for entry in entries:
        name = entry.artefact_name()
        entry_labels = " ".join(entry.labels.values()).lower()
        tied_to_a_fetch = any(
            _stem(name) == _stem(fetched) and fetched.lower() in entry_labels
            for fetched in fetched_names
        )
        assert name in fetched_names or tied_to_a_fetch, (
            f"{entry.label}: the artefact name {name!r} appears in no fetch list of §5.4 and "
            f"is derived from none it names; a release checklist cannot carry a file the "
            f"record gives no other account of"
        )

    # `nsis7z.dll` is the binary whose corresponding source is more than one file, and
    # the record says so by naming two entries with parts. A record that quietly
    # narrowed to the plug-in's own archive -- the narrower of the two readings §2.5.1
    # puts to the owner -- would still satisfy an "every binary has an entry" count.
    nsis7z = [entry for entry in entries if entry.binary == "nsis7z.dll"]
    assert len(nsis7z) == 2, (
        f"§2.5.1 carries {len(nsis7z)} delivery entries for nsis7z.dll; the record states "
        "two -- the plug-in's own release, and the archive that completes the 174 sources "
        "its project file compiles -- and that gap is a claim about bytes only two entries "
        "can carry"
    )
    assert all(entry.part for entry in nsis7z), (
        f"the nsis7z.dll entries carry parts {[entry.part for entry in nsis7z]}; two entries "
        "for one binary with no part labels are two records a reader cannot order"
    )


def test_the_delivery_record_is_measured_against_the_upstream_bytes_where_they_are(
    tmp_path: Path,
) -> None:
    """§2.5.1's hashes are checked against the real archives where they are on hand.

    **Why this is a separate case.** The record's sha256 values measure upstream
    files that are not in the checkout and cannot be. Comparing them with each other
    proves nothing about those bytes, so this case hashes the real archives against
    the record. Where they are not on the machine it says so and names the variable
    that would name them, rather than reporting a hash it never took.

    **And the mismatch arm runs first, and always.** It needs no upstream archive --
    the bytes are written into a temp directory -- so a runner that has none of the
    real material still sees this witness shown able to fail.
    """
    watch = _lgpl_delivery()
    notice_text = _notice_text()
    entries = watch.delivery_entries(notice_text)

    # Every artefact is planted, and each with the byte count §2.5.1 records for it.
    # That is what isolates the hash arm: planted files of the wrong size produce a
    # size report that also names sha256, and a witness satisfied by "some problem
    # mentions sha256" would stay green with the hash comparison neutered. With the
    # sizes right, the only thing left to report is the hash.
    planted = tmp_path / "planted"
    planted.mkdir()
    for entry in entries:
        name = entry.artefact_name()
        recorded_bytes = entry.recorded_bytes()
        assert name and recorded_bytes, f"{entry.label}: no artefact name or byte count to plant"
        (planted / name).write_bytes(b"\0" * recorded_bytes)
    wrong_hash = watch.check_against_directory(entries, planted)
    for entry in entries:
        name = entry.artefact_name()
        owned = [problem for problem in wrong_hash if name in problem]
        assert owned, (
            f"a planted {name} of the wrong bytes produced no problem naming it: {wrong_hash}"
        )
        assert all("sha256" in problem for problem in owned), (
            f"a planted {name} of the right size and the wrong contents produced a report that "
            f"never named sha256: {owned}"
        )
        assert not any("bytes;" in problem for problem in owned), (
            f"a planted {name} of the recorded size was reported as a size mismatch: {owned}"
        )

    # The missing-file arm, watched on its own: with one artefact absent, the report
    # must name that file rather than only the ones that were present.
    missing = tmp_path / "missing"
    missing.mkdir()
    absent = entries[-1]
    for entry in entries[:-1]:
        name = entry.artefact_name()
        assert name, f"{entry.label}: no artefact name to plant"
        (missing / name).write_bytes(b"\0" * (entry.recorded_bytes() or 1))
    gaps = watch.check_against_directory(entries, missing)
    gap_named = [problem for problem in gaps if absent.artefact_name() in problem]
    assert gap_named, f"an absent {absent.artefact_name()} produced no problem naming it: {gaps}"

    directory = _env_directory("LABCAIRN_LGPL_SOURCE_DIR")
    if directory is None:
        pytest.skip(
            "no directory of upstream source archives (LABCAIRN_LGPL_SOURCE_DIR names one; "
            f"§5.4's step 4b prints the fetches that fill it), so {len(entries)} recorded "
            "sha256 values were not measured against upstream bytes in this run"
        )
    problems = watch.check_against_directory(entries, directory)
    assert problems == [], (
        f"§2.5.1's recorded hashes are not the hashes of the archives: {problems}"
    )


def test_the_delivery_reader_refuses_a_record_that_states_nothing() -> None:
    """Each way the record can stop being performable reddens it, and names what it lost.

    **Why the controls are here.** Every case above is satisfied by an empty list of
    problems. A reader that collected nothing -- a §2.5.1 whose entries its patterns
    did not match, a §2.5 whose LGPL rows it did not see -- would report those as
    clean, and a green report about a record that said nothing is the failure this
    repository keeps having to name. So each way the record can fail to state a step
    is put to the same reader: an LGPL binary with no entry at all (the record's
    earlier shape), a sha256 whose shape is wrong, an entry missing its artefact, its
    URL or its stated point, a §2.5 that gains an LGPL binary §2.5.1 never heard of,
    and a §2.5.1 with no entries at all.
    """
    watch = _lgpl_delivery()
    notice_text = _notice_text()
    records = watch.binary_records(notice_text)
    entries = watch.delivery_entries(notice_text)

    # **The cut point is found by design or reported by design.** The arms below cut the
    # record at a delivery entry's heading. If the entry this line looks for has already
    # gone -- the record on disk was rewritten before the run -- a plain `str.index` would
    # crash the preparation here, and the failure a reader saw would be a traceback about
    # a substring rather than the sentence that says what vanished. The record failing to
    # state an entry is case (a) below; arriving at that case with the entry already gone
    # from the real file is the same defect, reported here.
    entry_heading = "    Delivery entry — `StdUtils.dll`"
    if entry_heading not in notice_text:
        pytest.fail(
            "NOTICE §2.5.1 carries no delivery entry for StdUtils.dll at all -- the record "
            "this witness reads has lost the entry the controls below cut and restore; "
            "case (a) below is that defect found in the record itself"
        )

    first_entry = notice_text.index(entry_heading)

    # (a) The entry for one binary deleted outright: the record before it was rewritten.
    following = notice_text.index("    Delivery entry — `nsis7z.dll`", first_entry)
    without_stdutils = notice_text[:first_entry] + notice_text[following:]
    assert "Delivery entry — `StdUtils.dll`" not in without_stdutils, (
        "the control did not remove the StdUtils.dll entry"
    )
    stripped_problems = watch.coverage_problems(
        watch.binary_records(without_stdutils), watch.delivery_entries(without_stdutils)
    )
    assert any("StdUtils.dll" in problem for problem in stripped_problems), (
        f"a §2.5.1 that stopped delivering a source for StdUtils.dll produced: {stripped_problems}"
    )

    # (b) A sha256 whose shape is wrong: the recorded value with one hex digit dropped.
    stdutils = next(item for item in entries if item.binary == "StdUtils.dll")
    recorded = stdutils.recorded_sha256()
    assert recorded is not None and len(recorded) == 64, "the real entry records no 64-digit sha256"
    damaged = notice_text.replace(recorded, recorded[:-1], 1)
    assert recorded not in damaged, "the control did not damage the sha256"
    damaged_problems = watch.coverage_problems(
        watch.binary_records(damaged), watch.delivery_entries(damaged)
    )
    assert any("sha256" in problem for problem in damaged_problems), (
        f"a §2.5.1 whose StdUtils.dll sha256 is 63 characters produced: {damaged_problems}"
    )

    # (c) Each remaining required field, removed one at a time.
    for label, expectation in (
        ("artefact", "names no file"),
        ("fetched", "no upstream URL"),
        ("at", "point at which"),
    ):
        mutated = _drop_delivery_label(notice_text, "StdUtils.dll", label)
        label_problems = watch.coverage_problems(
            watch.binary_records(mutated), watch.delivery_entries(mutated)
        )
        assert label_problems, f"a delivery entry missing its {label!r} label produced nothing"
        assert any(expectation in problem for problem in label_problems), (
            f"a delivery entry missing its {label!r} label produced: {label_problems}"
        )

    # (d) A §2.5 that gains an LGPL binary while §2.5.1 stays as it is.
    gained = notice_text.replace(
        "  nsis7z.dll — 434,176 bytes",
        "  Synth.dll — 1,024 bytes\n"
        "    path     $PLUGINSDIR\\Synth.dll\n"
        "    sha256   0000000000000000000000000000000000000000000000000000000000000000\n"
        "    bundle   somewhere\n"
        "    licence  LGPL-2.1\n"
        "    holder   nobody\n"
        "    where    nowhere\n\n"
        "  nsis7z.dll — 434,176 bytes",
        1,
    )
    assert "Synth.dll" in gained, "the control did not add a binary to §2.5"
    gained_records = watch.binary_records(gained)
    gained_lgpl = [item.name for item in gained_records if item.is_lgpl]
    assert "Synth.dll" in gained_lgpl, f"§2.5's new binary was not read as LGPL: {gained_lgpl}"
    gained_problems = watch.coverage_problems(gained_records, watch.delivery_entries(gained))
    assert any("Synth.dll" in problem for problem in gained_problems), (
        f"a §2.5 that gained an LGPL binary §2.5.1 never recorded produced: {gained_problems}"
    )

    # (e) A §2.5.1 with no delivery entries at all refuses rather than reporting clean.
    how = notice_text.index('\n\n    **How "corresponding source"')
    emptied = notice_text[:first_entry] + notice_text[how:]
    try:
        watch.delivery_entries(emptied)
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "a §2.5.1 carrying no delivery entry returned a list instead of refusing, and "
            "every case above would then be green over a record that delivered nothing"
        )

    # (f) A §2.5 whose binary blocks are gone: the reader refuses rather than reporting
    # an empty census. Without this arm, a reader that returned "no records" where the
    # section names eight would still satisfy every assertion above, because "no LGPL
    # binaries" and "no problems" are the same empty list to a coverage check.
    first_binary = notice_text.index("  StdUtils.dll — 102,400 bytes")
    census = notice_text.index("Two of the eight are therefore LGPL")
    emptied_binaries = notice_text[:first_binary] + notice_text[census:]
    assert "StdUtils.dll — 102,400 bytes" not in emptied_binaries, (
        "the control did not remove §2.5's binary blocks"
    )
    try:
        watch.binary_records(emptied_binaries)
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "a §2.5 naming no binary returned records instead of refusing; the delivery "
            "record would then watch nothing and report that as clean"
        )

    # The reader read something out of the real tree: the arms that ran are named.
    assert len(records) == 8, f"§2.5 read {len(records)} binaries; the record states eight"
    assert len(entries) >= 2, f"§2.5.1 read {len(entries)} delivery entries"


# ---------------------------------------------------------------------------
# Who decided how "corresponding source" is read, and the closure audit that
# re-measures the numbers the record prints about it.
#
# §2.5.1 recorded two defensible readings of LGPL-2.1 §4's "complete corresponding
# source code" for nsis7z.dll and put the choice to the owner; the owner decided it on
# 2026-11-13 that the corresponding source is the conjunction of the plug-in's own
# release archive and 7-Zip's source release. A decision that lives only in a chat log
# is not a record: the reading a distribution actually conveys has to be readable from
# the file that conveys it, and a record that still said "put to the owner" after the
# owner answered would be a record that lags the thing it records. §2.5.2's closure
# numbers are watched the same way -- by running the audit the record names, whose
# expected values it reads out of the record itself.
# ---------------------------------------------------------------------------


#: §2.5.1's heading for the paragraph that states the reading, as the record prints it.
DECIDED_HEADING: Final[str] = 'How "corresponding source" is read here, and who decided it.'

#: §2.5.1's sentence that names the decision and its date.
DECISION_SENTENCE: Final[str] = "**The owner decided this reading on 2026-11-13.**"

#: The words §2.5.1 and §2.5.2 used while the reading was open. Where the record
#: still uses them for the two matters the decision did not reach, they are correct;
#: where they stand in the paragraph that records the reading, the record lags the
#: decision it records. Hence the span check in `_reading_paragraph`, not a whole
#: section: a whole-section ban reddens a record that is right.
OPEN_READING_PHRASES: Final[tuple[str, ...]] = ("put to the owner", "not decided here")

#: §2.5.2's sentence closing the item, and the phrase it must have replaced.
DECIDED_ITEM: Final[str] = "**is no longer open: the owner decided it on 2026-11-13.**"

#: The closure numbers §2.5.1 and §2.5.2 printed when this case was written, measured on
#: the archives fetched 2026-11-13. Pinned as *observed* values, so a reader that bound a
#: claim to the wrong sentence -- the 166/175 the 7-Zip archive supplies rather than the
#: 166/176 absent from the plug-in archive -- reddens instead of agreeing with the record.
OBSERVED_CLOSURE: Final[dict[str, int]] = {
    "compiled_sources": 174,
    "named_headers": 185,
    "sources_absent_from_plugin": 166,
    "headers_absent_from_plugin": 176,
    "sources_supplied_by_sevenzip": 166,
    "headers_supplied_by_sevenzip": 175,
    "headers_in_neither": 1,
    "compiled_naming_rar": 0,
    "plugin_rar_files": 0,
    "dll_token_occurrences": 0,
    "sevenzip_rar_files": 9,
    "unrar_notice_bytes": 1921,
    "lzma_rar_files": 0,
}

#: The three extract directories `--audit-extracts` re-counts, under one variable.
EXTRACT_SUBDIRS: Final[tuple[str, ...]] = ("nsis7z", "7z1900", "lzma1900")


def _flat_section(watch: Any, notice_text: str, heading: str) -> str:
    """One NOTICE subsection as one run of text, with its wraps collapsed.

    The reader's own helper is used rather than a join written here: §2.5.1 and §2.5.2
    wrap their sentences, and a claim reader that matched a different shape would be a
    second reader that can disagree with the one the release runs.
    """
    return " ".join(watch._subsection(notice_text, heading).split())


#: §2.5.1's paragraph stating the reading runs to the not-yet-done paragraph.
DECISION_SPAN_START_251: Final[str] = 'How "corresponding source" is read here, and who decided it.'
DECISION_SPAN_END_251: Final[str] = "**What is not yet done.**"
DECISION_SPAN_START_252: Final[str] = "A third thing this section used to leave open"
DECISION_SPAN_END_252: Final[str] = "What the decision did not reach"


def _span(text: str, start: str, end: str, *, where: str) -> str:
    """One paragraph span of a flattened section, naming what was not found.

    The decision assertions are span assertions on purpose. §2.5.2 states, in the same
    section, two matters that are genuinely still open, and a ban over the whole section
    would redden a record that is correct. What has to be clean is the paragraph that
    records the reading itself.
    """
    from_ = text.find(start)
    if from_ < 0:
        raise AssertionError(
            f"{where} no longer carries {start!r}, so its wording is not locatable"
        )
    to = text.find(end, from_ + len(start))
    if to < 0:
        raise AssertionError(f"{where} no longer carries {end!r} after {start!r}")
    return text[from_:to]


#: §2.5.1's heading and §2.5.2's closing clause as they stood before the owner answered.
BEFORE_HEADING_251: Final[str] = 'How "corresponding source" is being read here'
BEFORE_CLOSE_252: Final[str] = "is a legal judgement §2.5.2 puts to the owner, not decided here"

#: §2.5.1's paragraph on the reading as it stood while the choice was open, quoted from
#: revision `1e59502` rather than paraphrased: the control has to be the wording the record
#: actually had, not an approximation of it.
OPEN_READING_PARAGRAPH: Final[str] = (
    "The narrower reading, that the plug-in's own release archive is the corresponding source "
    "because it is the upstream release the plug-in was taken from, is defensible too and is "
    "what the delivery entries would look like if it were adopted. Which reading this "
    "repository records is a legal judgement and is **put to the owner**, not decided here; "
    "§2.5.2 names it as open."
)


def _decision_taken_back_out(notice_text: str) -> str:
    """The whole revert: §2.5.1's heading, its decision sentence, §2.5.2's closing clause."""
    reverted = notice_text.replace(DECISION_SENTENCE, OPEN_READING_PARAGRAPH, 1)
    reverted = reverted.replace(DECIDED_HEADING, BEFORE_HEADING_251, 1)
    reverted = reverted.replace(DECIDED_ITEM, BEFORE_CLOSE_252, 1)
    assert reverted != notice_text, "the control changed nothing"
    return reverted


def _reading_reopened(notice_text: str) -> str:
    """§2.5.1's decision sentence alone, back to the open wording, its heading intact."""
    reopened = notice_text.replace(DECISION_SENTENCE, OPEN_READING_PARAGRAPH, 1)
    assert reopened != notice_text and DECIDED_HEADING in reopened, (
        "the control changed the wrong thing"
    )
    return reopened


def _item_reopened(notice_text: str) -> str:
    """§2.5.2's closing clause alone, back to the open wording."""
    reopened = notice_text.replace(DECIDED_ITEM, BEFORE_CLOSE_252, 1)
    assert reopened != notice_text, "the control changed nothing in §2.5.2"
    return reopened


def _everything_closed(notice_text: str) -> str:
    """The record with the two genuinely open matters written as settled.

    The opposite defect, and the one a wording witness invites: a section that closes
    everything passes an "the reading is decided" check by erasing what is still
    outstanding, so the section's ability to say something is open is itself watched.
    """
    closed = notice_text.replace("is likewise not decided here.", "is settled the same way.", 1)
    closed = closed.replace("recorded below as **measured facts**", "recorded below as settled", 1)
    closed = closed.replace("Recorded as measured fact since 2026-11-13; ", "", 1)
    assert closed != notice_text, "the control changed nothing in the open items"
    return closed


def _decision_problems(watch: Any, notice_text: str) -> list[str]:
    """What the record fails to state about the reading it keeps, one line per failure.

    Each line names the section it is about, which is what makes the controls below a
    demonstration of scope: reopening §2.5.1 must not report §2.5.2 as broken, and a
    record that legitimately leaves two matters open must not be reddened for doing so.
    """
    section_251 = _flat_section(watch, notice_text, "2.5.1")
    section_252 = _flat_section(watch, notice_text, "2.5.2")
    problems: list[str] = []

    try:
        reading = _span(section_251, DECISION_SPAN_START_251, DECISION_SPAN_END_251, where="§2.5.1")
    except AssertionError as error:
        problems.append(str(error))
        reading = ""
    try:
        closed = _span(section_252, DECISION_SPAN_START_252, DECISION_SPAN_END_252, where="§2.5.2")
    except AssertionError as error:
        problems.append(str(error))
        closed = ""

    if DECISION_SENTENCE not in reading:
        problems.append(
            f"§2.5.1 prints no {DECISION_SENTENCE!r} where it states the reading, so the "
            "delivery entries carry a legal choice the record attributes to nobody"
        )
    if DECIDED_ITEM not in closed:
        problems.append(
            f"§2.5.2 prints no {DECIDED_ITEM!r}; the section that defers investigations still "
            "presents the reading as one of the things it defers"
        )
    for phrase in OPEN_READING_PHRASES:
        if phrase in reading:
            problems.append(
                f"§2.5.1's paragraph on the reading still says {phrase!r} although the owner "
                "decided it on 2026-11-13; the record lags the decision it records"
            )
        if phrase in closed:
            problems.append(
                f"§2.5.2's paragraph closing the reading still says {phrase!r} although §2.5.1 "
                "records the decision"
            )
    if "**not** the reading this repository records" not in reading:
        problems.append(
            "§2.5.1 does not say which reading it declined, so both remain available to "
            "whoever prepares a release"
        )
    if "**not** the reading this repository keeps" not in closed:
        problems.append(
            "§2.5.2 names the alternative reading without saying the repository does not keep it"
        )

    # The two matters the decision did not reach have to stay stated as open, and anchored
    # to the date they were measured on.
    open_matters = section_252.split(DECISION_SPAN_END_252, 1)[-1]
    if not any(phrase in open_matters for phrase in OPEN_READING_PHRASES):
        problems.append(
            "§2.5.2 no longer says the Rar consequence and the one-header gap are undecided; "
            "a decision check is only trustworthy in a section that can still say something "
            "is open"
        )
    if "recorded below as **measured facts**" not in open_matters:
        problems.append(
            "§2.5.2 no longer says which of its items are measurements, so a count printed "
            "there is indistinguishable from an assertion"
        )
    if "Recorded as measured fact since 2026-11-13" not in open_matters:
        problems.append(
            "§2.5.2's one-header gap is no longer anchored to the date it was measured on, so "
            "the next window cannot tell whether it still holds"
        )
    return problems


def test_the_record_states_which_reading_of_corresponding_source_it_keeps() -> None:
    """§2.5.1 names the reading it keeps and who decided it; §2.5.2 no longer defers it.

    **The property.** LGPL-2.1 §4's "complete corresponding source code" has more than one
    defensible reading for `nsis7z.dll`, and the two produce different release pages: one
    archive, or two. The owner decided on 2026-11-13 that the corresponding source is the
    conjunction -- `Nsis7z_19.00.7z` **and** `7z1900-src.7z` -- and the smaller choice inside
    it, that a release carries 7-Zip's full source release rather than the LZMA SDK archive
    the plug-in's own build note names. What is watched is that the record states that
    decision where it states the reading, that the section which used to defer the reading no
    longer defers it, and that the same section still says plainly which matters remain open.

    **Why the wording is the thing under test.** Nothing else in the tree carries the
    decision: no artefact exists yet, so there are no bytes to compare the record with, and
    the delivery entries would look identical whether the record presented the reading as
    decided or as outstanding. A record that says "put to the owner" after the owner answered
    is a record that lags what it records, and the next window reading it puts the same
    question again.

    **Why the checks are per-paragraph.** §2.5.2 is the section that defers work, and two
    matters it defers are genuinely still open. A ban on open-question wording over the whole
    section would redden a record that is correct, and the tempting shortcut -- "no such
    phrase anywhere in §2.5.2" -- is the kind of assertion that stays green only because it
    mis-states what the record owes. So the span that records the decision is checked clean,
    and the span that lists the open items is checked for still containing open wording.

    **What this does not claim.** It does not say the reading is legally correct, and it does
    not say the Rar consequence or the one-header gap is answered: those stay open by design,
    and what is watched here is that they are recorded as measurements anchored to a date.
    """
    watch = _lgpl_delivery()
    notice_text = _notice_text()

    problems = _decision_problems(watch, notice_text)
    assert problems == [], f"the record does not state the decision it is built on: {problems}"

    # The reader read the record rather than a constant: the counts behind the open items.
    claim = watch.closure_claims(notice_text)
    assert claim.sevenzip_rar_files == OBSERVED_CLOSURE["sevenzip_rar_files"], (
        "§2.5.2 no longer states the count of Rar handlers the delivered archive carries, and "
        "that count is the fact the unRAR question is asked about"
    )

    # Control 1: the whole revert to the wording of revision 1e59502.
    reverted = _decision_taken_back_out(notice_text)
    reverted_problems = _decision_problems(watch, reverted)
    assert reverted_problems, "the record as it stood before the owner answered read as decided"
    assert any("§2.5.1" in problem for problem in reverted_problems), (
        f"the pre-decision §2.5.1 produced no §2.5.1 finding: {reverted_problems}"
    )
    assert any("§2.5.2" in problem for problem in reverted_problems), (
        f"the pre-decision §2.5.2 produced no §2.5.2 finding: {reverted_problems}"
    )

    # Control 2: only §2.5.1 reopened, so the finding is scoped to the right section.
    reopened_251 = _decision_problems(watch, _reading_reopened(notice_text))
    assert reopened_251 and all("§2.5.1" in problem for problem in reopened_251), (
        f"reopening §2.5.1 alone produced: {reopened_251}"
    )

    # Control 3: only §2.5.2's closing clause reopened.
    reopened_252 = _decision_problems(watch, _item_reopened(notice_text))
    assert reopened_252 and all("§2.5.2" in problem for problem in reopened_252), (
        f"reopening §2.5.2 alone produced: {reopened_252}"
    )

    # Control 4: the opposite defect -- a record that closes what is still open.
    closed_problems = _decision_problems(watch, _everything_closed(notice_text))
    assert any("undecided" in problem for problem in closed_problems), (
        f"a §2.5.2 that wrote the two open matters as settled produced: {closed_problems}"
    )
    assert any("which of its items are measurements" in problem for problem in closed_problems), (
        f"a §2.5.2 that stopped calling its items measurements produced: {closed_problems}"
    )
    assert any(
        "anchored to the date it was measured on" in problem for problem in closed_problems
    ), f"a §2.5.2 that dropped the gap's measurement date produced: {closed_problems}"


def test_the_closure_audit_reads_its_expected_values_out_of_the_record(
    tmp_path: Path,
) -> None:
    """`--audit-extracts` reads the numbers it checks from NOTICE, and reddens on disagreement.

    **The property.** §2.5.2 prints a closure record for `nsis7z.dll` -- 174 compiled
    sources and 185 headers listed by the plug-in's own project file, 166 and 176 of them
    absent from the plug-in's release archive, 166 and 175 supplied by 7-Zip's, one header
    in neither, no compiled source naming a Rar file, nine handlers and a 1,921-byte notice
    document in `7z1900-src.7z`, none in `lzma1900.7z`, and the shipped DLL carrying
    `Rar`/`NRar`/`unrar` zero times each. Those numbers are measurements of archives that
    are not in the checkout, so they rot the moment an upstream archive changes. The audit
    §2.5.2 names re-counts them, and for the audit to be a comparison rather than a mirror
    its expected values have to come from the record.

    **Why the arms are arranged as they are.** Two arms run on synthetic bytes and need no
    upstream archive, so a machine with none still sees the audit shown able to fail: a
    planted project whose counts disagree with the record, and a record whose stated counts
    are changed under a reader that reads them from the record's sentences. The arm that
    re-counts the real archives is the one that needs them, and it names the variable when
    they are not on hand instead of reporting counts it never took.
    """
    watch = _lgpl_delivery()
    notice_text = _notice_text()

    # (a) The reader read the record: every value it returns is the one printed.
    claim = watch.closure_claims(notice_text)
    for field, expected in OBSERVED_CLOSURE.items():
        actual = getattr(claim, field)
        assert actual == expected, (
            f"closure_claims read {field} as {actual}; §2.5.1/§2.5.2 print {expected}, so the "
            "reader is bound to some other sentence or a default is standing in for a claim"
        )

    # (b) The expected values come from the record: change a printed count and the reader
    # follows the record, not a constant.
    changed_record = notice_text.replace(
        "the 174 sources the archive's own `Nsis7z.vcxproj` compiles, 166",
        "the 174 sources the archive's own `Nsis7z.vcxproj` compiles, 167",
        1,
    ).replace(
        "contains **all nine** files of `CPP/7zip/Archive/Rar/`",
        "contains **all eight** files of `CPP/7zip/Archive/Rar/`",
        1,
    )
    assert changed_record != notice_text, "the control did not change the printed counts"
    re_read = watch.closure_claims(changed_record)
    assert re_read.sources_absent_from_plugin == 167 and claim.sources_absent_from_plugin == 166, (
        "the reader kept 166 after §2.5.1 was changed to 167: the audit would then compare the "
        "archives with its own constants"
    )
    assert re_read.sevenzip_rar_files == 8 and claim.sevenzip_rar_files == 9, (
        "the reader kept nine after §2.5.2 was changed to eight"
    )

    # (c) A record that stops stating a claim refuses rather than defaulting it.
    silent = notice_text.replace(
        "contains **all nine** files of `CPP/7zip/Archive/Rar/` and a\n    1,921-byte",
        "contains the Rar handlers and a notice document,",
        1,
    )
    assert silent != notice_text, "the control did not remove the Rar counts from §2.5.2"
    try:
        watch.closure_claims(silent)
    except RuntimeError as error:
        assert "Rar" in str(error), f"the refusal did not name what it could not read: {error}"
    else:
        raise AssertionError(
            "closure_claims returned a count for a §2.5.2 that states none; a missing claim "
            "would then be audited against a number nobody measured"
        )

    # (c2) A count written as a word the reader does not know: refuse, do not guess.
    unparseable = notice_text.replace(
        "the plug-in's own release archive contains **no file named\n    `*Rar*` at all**",
        "the plug-in's own release archive contains **zero file named\n    `*Rar*` at all**",
        1,
    )
    assert unparseable != notice_text, "the control did not change the plug-in archive's count word"
    try:
        watch.closure_claims(unparseable)
    except RuntimeError as error:
        assert "plug-in archive" in str(error), f"the refusal did not name the claim: {error}"
    else:
        raise AssertionError(
            "closure_claims accepted a count word it does not know; an unparseable claim would "
            "then be audited against whatever the reader defaulted to"
        )

    # (c3) And the count is read out of the sentence, not hard-coded from its shape: state a
    # different number in the same sentence and the reader follows it.
    stated = notice_text.replace(
        "the plug-in's own release archive contains **no file named\n    `*Rar*` at all**",
        "the plug-in's own release archive contains **three files named\n    `*Rar*` at all**",
        1,
    )
    assert stated != notice_text, "the control did not state a count in the plug-in claim"
    assert watch.closure_claims(stated).plugin_rar_files == 3, (
        "the reader reported 0 for a §2.5.2 that states three: a hard-coded zero would keep "
        "reporting the plug-in archive as Rar-free whatever the record said"
    )

    # (d) The comparison runs: a planted extract tree whose counts are the record's
    # numbers is reported as a disagreement, and a tree with no shipped binary is reported
    # as not measured rather than as a zero.
    planted = tmp_path / "planted"
    project_dir = planted / "Contrib" / "nsis7z" / "CPP" / "7zip" / "Bundles" / "Nsis7z"
    project_dir.mkdir(parents=True)
    project_dir.joinpath("Nsis7z.vcxproj").write_text(
        "<Project><ItemGroup>"
        '<ClCompile Include="..\\..\\..\\..\\C\\LzmaLib.cpp" />'
        '<ClCompile Include="..\\..\\Archive\\SevenZip\\Nsis7z.cpp" />'
        '<ClInclude Include="..\\..\\Common\\MyUnknown.h" />'
        "</ItemGroup></Project>\n",
        encoding="utf-8",
    )
    empty_sevenzip = tmp_path / "empty-sevenzip"
    empty_sevenzip.mkdir()
    lines, problems = watch.audit_extracts(
        claim,
        watch.binary_records(notice_text),
        planted,
        empty_sevenzip,
        None,
    )
    assert problems, "the audit reported clean over an extract tree that lists two sources"
    joined = "\n".join(problems)
    assert "compiled sources the project lists" in joined and "174" in joined, (
        f"the audit did not report the compiled-source census it was given: {problems}"
    )
    assert "files named *Rar* in lzma1900.7z" in joined, (
        f"the audit did not report the LZMA SDK count it could not measure: {problems}"
    )
    assert "was not re-measured" in "\n".join(lines), (
        f"the audit let an unmeasured count pass without saying so: {lines}"
    )

    missing_extract_lines, missing_extract_problems = watch.audit_extracts(
        claim,
        watch.binary_records(notice_text),
        tmp_path / "no-such-extract",
        empty_sevenzip,
        None,
    )
    assert missing_extract_problems and "no directory" in "\n".join(missing_extract_problems), (
        f"the audit accepted an extract directory that does not exist: {missing_extract_problems}"
    )
    assert missing_extract_lines == [], (
        f"the audit printed counts for archives it never opened: {missing_extract_lines}"
    )

    # (d2) The command's own shape: the refusal that names the argument count. A CLI that
    # accepted one directory, or four, would run the audit over the wrong pair of archives
    # and report a comparison nobody asked for.
    one_directory = subprocess.run(
        [sys.executable, str(_lgpl_script_path()), "--audit-extracts", str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert one_directory.returncode == 2, (
        f"--audit-extracts with one directory exited {one_directory.returncode} instead of "
        f"refusing:\n{one_directory.stdout}\n{one_directory.stderr}"
    )
    assert "takes two directories" in one_directory.stderr, (
        f"the refusal did not say what it takes: {one_directory.stderr}"
    )
    four_directories = subprocess.run(
        [
            sys.executable,
            str(_lgpl_script_path()),
            "--audit-extracts",
            str(tmp_path),
            str(tmp_path),
            str(tmp_path),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert four_directories.returncode == 2, (
        f"--audit-extracts with four directories exited {four_directories.returncode} "
        f"instead of refusing:\n{four_directories.stderr}"
    )

    # (e) And the arm that needs the archives: the record against the bytes it describes.
    extracts = _env_directory("LABCAIRN_LGPL_EXTRACT_DIR")
    if extracts is None or not all((extracts / name).is_dir() for name in EXTRACT_SUBDIRS):
        pytest.skip(
            "LABCAIRN_LGPL_EXTRACT_DIR does not name a directory holding the unpacked "
            f"{'/'.join(EXTRACT_SUBDIRS)} archives, so §2.5.2's closure numbers were not "
            "re-counted against the upstream bytes here; arms (a)-(d) ran regardless"
        )
    script = _lgpl_script_path()
    run = subprocess.run(
        [
            sys.executable,
            str(script),
            "--audit-extracts",
            str(extracts / "nsis7z"),
            str(extracts / "7z1900"),
            str(extracts / "lzma1900"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert run.returncode == 0, (
        f"the closure audit against the real archives exited {run.returncode}:\n"
        f"{run.stdout}\n{run.stderr}"
    )
    pairs = re.findall(r"record (\d+), measured (\d+)", run.stdout)
    assert len(pairs) >= 12, (
        f"the audit printed {len(pairs)} record/measured pairs; §2.5.2 prints twelve counts to "
        f"re-measure:\n{run.stdout}"
    )
    assert all(recorded == measured for recorded, measured in pairs), (
        f"the audit printed a pair it did not report as a disagreement: {pairs}"
    )
    assert "CPP/7zip/IMyUnknown.h" in run.stdout, (
        f"the audit did not name the header §2.5.1 records as in neither archive:\n{run.stdout}"
    )

    # (f) The same audit over a record whose count no longer matches those bytes.
    doctored = notice_text.replace(
        "1,921-byte `DOC/unRarLicense.txt`", "1,920-byte `DOC/unRarLicense.txt`", 1
    )
    assert doctored != notice_text, "the control did not change the notice document's byte count"
    doctored_notice = tmp_path / "NOTICE-doctored"
    doctored_notice.write_text(doctored, encoding="utf-8")
    red = subprocess.run(
        [
            sys.executable,
            str(script),
            "--notice",
            str(doctored_notice),
            "--audit-extracts",
            str(extracts / "nsis7z"),
            str(extracts / "7z1900"),
            str(extracts / "lzma1900"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert red.returncode == 1, (
        f"an audit over a record whose unRarLicense byte count is wrong exited "
        f"{red.returncode}; the record and the bytes were compared and nothing was "
        f"reported:\n{red.stdout}\n{red.stderr}"
    )
    assert "unRarLicense" in red.stderr, (
        f"the audit reddened without naming the count that disagrees: {red.stderr}"
    )


# ---------------------------------------------------------------------------
# NOTICE §2.5.1's replaceability record — LGPL-2.1 §6(b).
#
# §2.5.1 used to record replaceability as NOT MEASURED, and the witness for that was
# the absence of one: a record that says "not measured" needs no evidence, so nothing
# in the tree could tell a careful refusal to claim apart from a claim nobody checked.
# On 2026-11-13 the item became a measurement, and with it came the parts that can
# rot: a date, three modified plug-ins with their sha256 values, four installers with
# the exit codes their runs returned, four observation files the installs wrote, and a
# paragraph saying what none of it shows.
#
# `scripts/lgpl_replaceability.py` is the reader, and it is run rather than
# paraphrased, for the reason the delivery record above states: a witness that
# re-derived the patterns would be a second copy, and the second copy can drift from
# the one a release actually runs.
#
# What is watched is the shape §2.5.1 owes a reader when it states a measurement:
# either the item states no measurement, in which case it asks for nothing, or it
# states one with its date, its bytes, its runs and its observed difference, each
# named so that a hollow version of it reddens. The controls hollow it out one piece
# at a time.
# ---------------------------------------------------------------------------

_REPLACEABILITY_READER: dict[str, Any] = {}


def _replaceability_script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts" / "lgpl_replaceability.py"


def _replaceability_reader() -> Any:
    """`scripts/lgpl_replaceability.py`, loaded the way the tool is run."""
    if "module" not in _REPLACEABILITY_READER:
        script = _replaceability_script_path()
        spec = importlib.util.spec_from_file_location("lgpl_replaceability_for_witness", script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _REPLACEABILITY_READER["module"] = module
    return _REPLACEABILITY_READER["module"]


#: What §2.5.1 names for its §6(b) measurement, counted from the record rather than
#: asserted from the licence: a reader that matched no claim at all would print
#: `0 modified plug-ins` and, without these figures, agree with itself.
REPLACEABILITY_VARIANTS: Final[tuple[str, ...]] = (
    "StdUtils.bytepatched.dll",
    "StdUtils.flagpatched.dll",
    "StdUtils.authored.dll",
)
REPLACEABILITY_OBSERVATIONS: Final[tuple[str, ...]] = (
    "observations-orig.txt",
    "observations-stamp.txt",
    "observations-flag.txt",
    "observations-replacement.txt",
)
REPLACEABILITY_INSTALLER_ROWS: Final[int] = 4

#: §2.5.1's own words for the limits of its measurement — the part of the record that
#: keeps a measured claim from reading as a verified one.
REPLACEABILITY_LIMITS: Final[str] = "**What this evidence does not show.**"


def _variant_sha_named_by_the_record(notice_text: str) -> str:
    """One sha256 §2.5.1 records for a modified plug-in, read out of the record.

    Read rather than written here so that the damaged-hash control always damages a value
    the record states. A constant copied from the record is a second copy, and it drifts:
    with one held here the control's own guard trips on a changed record instead of the
    record being caught, which is a different — and weaker — failure.
    """
    watch = _replaceability_reader()
    claims = watch.variant_claims(notice_text)
    assert claims, "§2.5.1 names no modified plug-in, so there is no recorded hash to damage"
    recorded: str | None = next(
        (claim.recorded_sha256 for claim in claims if claim.recorded_sha256 is not None), None
    )
    assert recorded is not None and len(recorded) == 64, (
        f"no modified plug-in §2.5.1 names carries a 64-character sha256: "
        f"{[(claim.name, claim.recorded_sha256) for claim in claims]}"
    )
    return recorded


def _run_replaceability_tool(
    *extra: str,
    notice: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """The reader, run as a command, with its exit code read from the process."""
    command = [sys.executable, str(_replaceability_script_path())]
    if notice is not None:
        command += ["--notice", str(notice)]
    command += list(extra)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _state_rewritten(notice_text: str, replacement: str) -> str:
    """§2.5.1's replaceability item with its state replaced."""
    damaged = notice_text.replace("    MEASURED 2026-11-13.**", f"    {replacement}.**", 1)
    assert damaged != notice_text, "the control did not change the replaceability state"
    return damaged


def _variant_sha_damaged(notice_text: str) -> str:
    """One sha256 §2.5.1 records, with its last hex digit removed."""
    recorded = _variant_sha_named_by_the_record(notice_text)
    damaged = notice_text.replace(recorded, recorded[:-1], 1)
    assert damaged != notice_text, "the control did not shorten a sha256 the record states"
    return damaged


def _variant_hashed_to_the_shipped_bytes(notice_text: str) -> str:
    """One modified plug-in given the shipped file's own sha256.

    The shape a record gets when an entry is filled in from the wrong row: the plug-in is
    named as modified and hashed to unmodified bytes, and every number still looks
    well-formed. Only a comparison against §2.5's own entry can see it.
    """
    watch = _replaceability_reader()
    shipped = watch.shipped_plugin_sha256(notice_text)
    assert shipped is not None, "§2.5 states no sha256 for StdUtils.dll to copy into the control"
    recorded = _variant_sha_named_by_the_record(notice_text)
    damaged = notice_text.replace(recorded, shipped, 1)
    assert damaged != notice_text, "the control did not replace a variant's sha256"
    return damaged


def _observations_dropped(notice_text: str) -> str:
    """§2.5.1 with its observation entries removed, hashes and all."""
    damaged = re.sub(
        r" {6}\* `observations-[a-z]+\.txt` — [\d,]+ bytes, sha256\n {8}`[0-9a-f]{64}`\n",
        "",
        notice_text,
    )
    assert damaged != notice_text, "the control removed no observation entry"
    assert all(name not in damaged for name in REPLACEABILITY_OBSERVATIONS), (
        "the control left an observation entry in the record"
    )
    return damaged


def _installers_dropped(notice_text: str) -> str:
    """§2.5.1's installer table with its rows removed and its header left standing."""
    damaged = re.sub(
        r"^ +\| (?:control, shipped bytes|with `[a-z]+`) \|.*\|\n",
        "",
        notice_text,
        flags=re.MULTILINE,
    )
    assert damaged != notice_text, "the control removed no installer row"
    assert "124,564,299" not in damaged, "the control left an installer row in the record"
    return damaged


def _exit_made_nonzero(notice_text: str) -> str:
    """One installer's stated install exit changed from 0 to 1: its run having failed."""
    damaged = notice_text.replace("| `b72e9013…` | 0 | 91 | 0 |", "| `b72e9013…` | 1 | 91 | 0 |", 1)
    assert damaged != notice_text, "the control did not change the recorded exit code"
    return damaged


def _limits_reworded(notice_text: str) -> str:
    """The limits paragraph's heading turned into a claim of coverage."""
    damaged = notice_text.replace(REPLACEABILITY_LIMITS, "**What this evidence shows.**", 1)
    assert damaged != notice_text, "the control did not reword the limits paragraph"
    return damaged


def _hashes_the_record_itself_prints(notice_text: str) -> list[str]:
    """Every sha256 §2.5.1's replaceability item states, table rows included.

    A control that retargets a prefix has to miss all of them, so it is written against the
    record's own values rather than against a list held here — a list held here would go
    stale against a record that gained an artefact.
    """
    watch = _replaceability_reader()
    values: list[str] = [
        claim.recorded_sha256
        for claim in watch.variant_claims(notice_text) + watch.observation_claims(notice_text)
        if claim.recorded_sha256 is not None
    ]
    values.extend(row.recorded_sha256 for row in watch.installer_rows(notice_text))
    shipped = watch.shipped_plugin_sha256(notice_text)
    if shipped is not None:
        values.append(shipped)
    assert values, f"§2.5.1 states no sha256 to retarget a prefix away from: {values}"
    return values


def _table_prefix_that_names_no_plug_in(notice_text: str) -> str:
    """One installer row given a plug-in prefix no plug-in in the record hashes to.

    The table names each plug-in by an eight-character prefix. A prefix that begins with
    nothing the item names is the shape a row copied from another build leaves: the row
    still states a plug-in, a byte count and two exit codes, and every field reads
    well-formed. Only a comparison against the hashes the item itself prints can see that it
    names none.
    """
    watch = _replaceability_reader()
    rows = watch.installer_rows(notice_text)
    assert len(rows) == REPLACEABILITY_INSTALLER_ROWS, (
        f"§2.5.1's table reads as {len(rows)} rows, not {REPLACEABILITY_INSTALLER_ROWS}, so "
        "there is no whole row to retarget"
    )
    hashes = _hashes_the_record_itself_prints(notice_text)
    candidate = next(
        (
            f"{value:08x}"
            for value in range(0x0100_0000, 0x0200_0000)
            if not any(hash_value.startswith(f"{value:08x}") for hash_value in hashes)
        ),
        None,
    )
    assert candidate is not None, "every eight-character prefix in that range is used"

    row = rows[1]
    line_start = notice_text.index(f"| {row.label} |")
    old_cell = f"| `{row.plugin_sha_prefix}…` |"
    cell = notice_text.index(old_cell, line_start)
    damaged = notice_text[:cell] + f"| `{candidate}…` |" + notice_text[cell + len(old_cell) :]
    assert damaged != notice_text, "the control did not retarget a table row's plug-in prefix"
    assert not any(hash_value.startswith(candidate) for hash_value in hashes), (
        f"the retargeted prefix {candidate} is one the record already uses"
    )
    return damaged


def _table_hex_value_one_character_short(notice_text: str) -> str:
    """One installer row's sha256 with its last digit dropped and its backtick lost.

    The shape a transcription error leaves, and the one every other check in the reader is
    blind to by construction: the row's plug-in prefix, exit codes and file count are
    untouched, and a field that requires exactly 64 hex digits simply stops matching, so a
    reader that only looks at fields would report that the table has fewer rows — a different
    claim — while the misprinted hash went unmentioned. What can report it is a reader that
    looks at every hex value the section prints and asks whether each is the length it states.
    """
    watch = _replaceability_reader()
    rows = watch.installer_rows(notice_text)
    assert len(rows) == REPLACEABILITY_INSTALLER_ROWS, (
        f"§2.5.1's table reads as {len(rows)} rows, not {REPLACEABILITY_INSTALLER_ROWS}, so "
        "there is no whole hash to shorten"
    )
    row = rows[1]
    line_start = notice_text.index(f"| {row.label} |")
    old_cell = f"| `{row.recorded_sha256}` |"
    cell = notice_text.index(old_cell, line_start)
    damaged = (
        notice_text[:cell] + f"| {row.recorded_sha256[:-1]}\n" + notice_text[cell + len(old_cell) :]
    )
    assert damaged != notice_text, "the control did not shorten a hash the table states"
    assert row.recorded_sha256 not in damaged, "the control left the full hash in the record"
    return damaged


def _artefacts_at_recorded_sizes(notice_text: str, directory: Path) -> list[str]:
    """Files named for every artefact §2.5.1 names, each one the recorded byte count.

    The contents are not the recorded contents — no file written here can be, and none
    pretends to be. Matching the sizes is what isolates the comparison: with the byte
    counts right, the only disagreement the reader can report is the sha256.
    """
    watch = _replaceability_reader()
    claims = watch.variant_claims(notice_text) + watch.observation_claims(notice_text)
    names: list[str] = []
    for index, claim in enumerate(claims):
        # A distinct fill byte per artefact. Two claims can state the same size — two of
        # §2.5.1's plug-ins are both 102,400 bytes — and files that are identical have
        # identical hashes, which would make one claim's replacement look like another's
        # content already being recorded.
        (directory / claim.name).write_bytes(bytes([65 + index]) * claim.recorded_bytes)
        names.append(claim.name)
    return names


def test_the_replaceability_record_states_a_route_or_a_measurement_with_its_evidence(
    tmp_path: Path,
) -> None:
    """§2.5.1's §6(b) item is either unmeasured or a dated measurement that carries proof.

    **The property.** A replaceability item does two different jobs, and which one it is
    doing changes what a reader may infer from it. `NOT MEASURED` records a route and
    forbids an inference; `MEASURED <date>` records runs, bytes and an observed
    difference, and invites one. What is watched is that the item is one or the other, and
    that the measured shape carries the parts a measured claim is made of: a date, the
    modified plug-ins with their sha256 values, the installers built with them and the
    exit codes of their runs, the files the installs wrote to show the modified plug-in was
    the one used, and a paragraph stating what none of it shows.

    **Why the other shape is run too.** A witness that only reddens a hollow measurement
    never accepts any record, and so cannot tell a complete record from a refusal — and the
    refusal is the shape this repository held until 2026-11-13. The alternative is put
    through the same reader and required to pass.

    **What is not claimed here.** Nothing in this test says the §6(b) route is legally
    satisfied, that the authored plug-in is interface-compatible in the sense the licence
    uses, or that a third party can obtain the means to build one. Those are §2.5.1's own
    limits, stated in the paragraph the reader requires it to find.
    """
    watch = _replaceability_reader()
    notice_text = _notice_text()

    # (a) The reader read the record rather than a constant it was handed.
    state = watch.replaceability_state(notice_text)
    assert state.startswith("MEASURED"), f"§2.5.1 states replaceability as {state!r}"
    assert re.search(r"20\d{2}-\d{2}-\d{2}", state), (
        f"§2.5.1 states {state!r} with no date inside the state itself"
    )

    variants = watch.variant_claims(notice_text)
    observations = watch.observation_claims(notice_text)
    rows = watch.installer_rows(notice_text)
    assert len(variants) == len(REPLACEABILITY_VARIANTS), (
        f"the reader found {len(variants)} modified plug-ins; §2.5.1 names "
        f"{len(REPLACEABILITY_VARIANTS)}, so the read is not reading the record"
    )
    assert {claim.name for claim in variants} == set(REPLACEABILITY_VARIANTS), (
        f"the reader named {sorted(claim.name for claim in variants)}, not the plug-ins "
        "§2.5.1 names"
    )
    assert all(
        claim.recorded_sha256 is not None and len(claim.recorded_sha256) == 64 for claim in variants
    ), "a modified plug-in §2.5.1 names carries no 64-character sha256"
    assert all(claim.recorded_bytes > 0 for claim in variants), (
        "a modified plug-in §2.5.1 names carries no byte count"
    )
    assert len(rows) == REPLACEABILITY_INSTALLER_ROWS, (
        f"the reader found {len(rows)} installer rows; §2.5.1's table states "
        f"{REPLACEABILITY_INSTALLER_ROWS}"
    )
    assert all(row.install_exit == "0" and row.uninstall_exit == "0" for row in rows), (
        "an installer row states a run that did not complete: "
        f"{[(row.label, row.install_exit, row.uninstall_exit) for row in rows]}"
    )
    assert all(row.installed_files > 0 for row in rows), (
        f"an installer row states no installed files: {[row.label for row in rows]}"
    )
    assert all(len(row.plugin_sha_prefix) == 8 for row in rows), (
        "an installer row states no plug-in identity to match the variant claims against"
    )
    assert len(observations) == len(REPLACEABILITY_OBSERVATIONS), (
        f"the reader found {len(observations)} observation files; §2.5.1 names "
        f"{len(REPLACEABILITY_OBSERVATIONS)}"
    )
    assert {claim.name for claim in observations} == set(REPLACEABILITY_OBSERVATIONS), (
        f"the reader named {sorted(claim.name for claim in observations)}, not the files "
        "§2.5.1 says the installs produced"
    )
    assert REPLACEABILITY_LIMITS in watch.replaceability_section(notice_text), (
        "§2.5.1 states a replaceability measurement with no paragraph saying what it does not show"
    )

    # (b) The reader runs as a command over the real record and prints what it read.
    completed = _run_replaceability_tool()
    assert completed.returncode == 0, (
        f"scripts/lgpl_replaceability.py exited {completed.returncode}:\n{completed.stdout}\n"
        f"{completed.stderr}"
    )
    printed = completed.stdout
    for name in REPLACEABILITY_VARIANTS + REPLACEABILITY_OBSERVATIONS:
        assert name in printed, f"the reader printed no {name!r}:\n{printed}"
    for claim in variants:
        assert claim.recorded_sha256 is not None
        assert claim.recorded_sha256 in printed, (
            f"the reader printed no {claim.recorded_sha256} for {claim.name}:\n{printed}"
        )
    assert f"installers built with them: {REPLACEABILITY_INSTALLER_ROWS}" in printed, (
        f"the reader printed no installer count:\n{printed}"
    )
    assert "the record states what the measurement does not show" in printed, (
        f"the reader printed no finding about the measurement's limits:\n{printed}"
    )

    # (c) The alternative shape: a record stating no measurement passes, and says so in
    #     words a reader of NOTICE would recognise.
    unmeasured = _state_rewritten(notice_text, "NOT MEASURED")
    unmeasured_notice = tmp_path / "NOTICE-unmeasured"
    unmeasured_notice.write_text(unmeasured, encoding="utf-8")
    unmeasured_run = _run_replaceability_tool(notice=unmeasured_notice)
    assert unmeasured_run.returncode == 0, (
        f"a §2.5.1 that states no measurement was refused ({unmeasured_run.returncode}):\n"
        f"{unmeasured_run.stdout}\n{unmeasured_run.stderr}"
    )
    assert "NOT MEASURED" in unmeasured_run.stdout, (
        f"the reader did not print the state it read: {unmeasured_run.stdout}"
    )
    assert watch.record_problems(unmeasured) == [], (
        "a record that claims no measurement produced findings: "
        f"{watch.record_problems(unmeasured)}"
    )

    # (d) The state grammar is real: an item stating neither thing is refused rather than
    #     silently read as one of them.
    directionless = _state_rewritten(notice_text, "SEE THE PARAGRAPHS BELOW")
    directionless_notice = tmp_path / "NOTICE-directionless"
    directionless_notice.write_text(directionless, encoding="utf-8")
    refused = _run_replaceability_tool(notice=directionless_notice)
    assert refused.returncode == 1, (
        f"an item stating no recognised state exited {refused.returncode}; the reader "
        f"accepted it:\n{refused.stdout}"
    )
    assert "no replaceability item" in refused.stderr, (
        f"the reader refused without saying why: {refused.stderr}"
    )


def test_the_replaceability_measurement_reds_when_any_part_of_its_proof_is_removed(
    tmp_path: Path,
) -> None:
    """Each part of §2.5.1's §6(b) measurement is load-bearing, one control per part.

    **Why per-part controls rather than a summary check.** The record's strength is that
    every claim points at a measurement: the date at a run, each sha256 at bytes, each exit
    code at a process, each observation file at a difference an install produced. A witness
    that only checked "the record mentions sha256 somewhere" survives a record whose hashes
    were stripped from the plug-ins and left in a neighbouring section. So each piece is
    removed on its own and the reader has to name the piece that went.

    **The byte comparison is shown able to fail, on bytes this test writes.** The artefacts
    §2.5.1 hashes are installer outputs and do not live in the checkout, so the arm that
    runs everywhere hands the reader files with the recorded byte counts and different
    contents: with the sizes matching, the only disagreement available to report is the
    hash, and the run has to report exactly that. Where `LABCAIRN_REPLACEABILITY_DIR` names
    the real artefacts, the same flag is run against them and required to agree.
    """
    watch = _replaceability_reader()
    notice_text = _notice_text()

    controls: dict[str, str] = {
        "a state with no date": _state_rewritten(notice_text, "MEASURED"),
        "a variant whose sha256 is damaged": _variant_sha_damaged(notice_text),
        "a variant hashed to the shipped file": _variant_hashed_to_the_shipped_bytes(notice_text),
        "no observation entries": _observations_dropped(notice_text),
        "no installer rows": _installers_dropped(notice_text),
        "an installer whose install run failed": _exit_made_nonzero(notice_text),
        "a limits heading reworded into a claim": _limits_reworded(notice_text),
        "a table row naming a plug-in nothing hashes to": _table_prefix_that_names_no_plug_in(
            notice_text
        ),
        "a table hash one character short": _table_hex_value_one_character_short(notice_text),
    }

    findings: dict[str, list[str]] = {}
    for label, damaged in controls.items():
        assert damaged != notice_text, f"the {label} control changed nothing"
        problems = watch.record_problems(damaged)
        assert problems, f"the record with {label} produced no finding"
        findings[label] = problems

    # Each control has to be caught by a finding about *its* piece, not by some other.
    assert any("no date" in problem for problem in findings["a state with no date"]), (
        f"the missing date produced no date finding: {findings['a state with no date']}"
    )
    assert any(
        "StdUtils.bytepatched.dll" in problem and "sha256" in problem
        for problem in findings["a variant whose sha256 is damaged"]
    ), (
        "the damaged sha256 produced no finding naming the plug-in and the hash: "
        f"{findings['a variant whose sha256 is damaged']}"
    )
    assert any(
        "the sha256 §2.5 records for the shipped file" in problem
        for problem in findings["a variant hashed to the shipped file"]
    ), (
        "a modified plug-in hashed to the shipped file's own sha256 produced no finding: "
        f"{findings['a variant hashed to the shipped file']}"
    )
    assert any(
        "no observed difference" in problem for problem in findings["no observation entries"]
    ), (
        "removing the observations produced no finding about the observed difference: "
        f"{findings['no observation entries']}"
    )
    assert any("no installer built" in problem for problem in findings["no installer rows"]), (
        f"removing the installer rows produced no finding about the installs: "
        f"{findings['no installer rows']}"
    )
    assert any(
        "exit 1" in problem and "completed the installation" in problem
        for problem in findings["an installer whose install run failed"]
    ), (
        "the failed install produced no finding naming the exit code: "
        f"{findings['an installer whose install run failed']}"
    )
    assert any(
        "does not show" in problem for problem in findings["a limits heading reworded into a claim"]
    ), (
        f"the reworded limits heading produced no finding naming it: "
        f"{findings['a limits heading reworded into a claim']}"
    )
    assert any(
        "no plug-in the item names hashes to" in problem
        for problem in findings["a table row naming a plug-in nothing hashes to"]
    ), (
        "a table row whose plug-in prefix nothing hashes to produced no finding naming the "
        f"prefix: {findings['a table row naming a plug-in nothing hashes to']}"
    )
    assert any(
        "63-character hex value" in problem
        for problem in findings["a table hash one character short"]
    ), (
        "a table hash with one character dropped produced no finding naming the value and its "
        f"length: {findings['a table hash one character short']}"
    )

    # The record as it stands produces no finding at all: the controls reddened because of
    # what was removed, not because the reader reports something of its own.
    assert watch.record_problems(notice_text) == [], (
        f"the record as it stands produced findings: {watch.record_problems(notice_text)}"
    )

    # The byte comparison, on bytes written here: recorded sizes, different contents.
    artefacts = tmp_path / "artefacts"
    artefacts.mkdir()
    names = _artefacts_at_recorded_sizes(notice_text, artefacts)
    assert len(names) == len(REPLACEABILITY_VARIANTS) + len(REPLACEABILITY_OBSERVATIONS), (
        f"the byte arm wrote {len(names)} artefacts, not one per claim §2.5.1 states"
    )
    mismatched = _run_replaceability_tool("--check-artefacts", str(artefacts))
    assert mismatched.returncode == 1, (
        f"the reader hashed {len(names)} files whose contents are not the recorded bytes and "
        f"exited {mismatched.returncode}; the hash comparison is not comparing:\n"
        f"{mismatched.stdout}\n{mismatched.stderr}"
    )
    reported = mismatched.stderr
    assert reported.count("records sha256") == len(names), (
        f"the reader reported {reported.count('records sha256')} hash disagreements for "
        f"{len(names)} artefacts:\n{reported}"
    )
    for name in names:
        assert name in reported, f"the hash disagreement named no {name!r}:\n{reported}"

    # The same mechanism has to be able to *agree*, on bytes this test controls. A record
    # whose hashes are rewritten to the files written above is the mirror of the run above:
    # the sizes already matched, so agreement here and disagreement there can only come from
    # the hashes. A reader that never reports a match and a reader that never reports a
    # mismatch both fail this arm.
    agreeing_text = notice_text
    rewritten_prefixes: dict[str, str] = {}
    for claim in watch.variant_claims(notice_text) + watch.observation_claims(notice_text):
        if claim.recorded_sha256 is None:
            continue
        actual = hashlib.sha256((artefacts / claim.name).read_bytes()).hexdigest()
        assert actual not in agreeing_text, (
            f"the file written for {claim.name!r} hashes to a value the record already "
            "states, so the agreement control would change nothing"
        )
        agreeing_text = agreeing_text.replace(claim.recorded_sha256, actual, 1)
        # Only a plug-in's hash is also quoted short, in the installer table; an
        # observation file's hash appears once. The prefixes are followed where the
        # record quotes them, and nowhere else.
        if f"`{claim.recorded_sha256[:8]}…`" in agreeing_text:
            rewritten_prefixes[claim.recorded_sha256[:8]] = actual[:8]
    assert agreeing_text != notice_text, "the agreement control rewrote no recorded hash"

    # §2.5.1's table names each plug-in by an eight-character prefix. Rewriting the full
    # hashes alone would leave those prefixes pointing at nothing, and the run would then
    # fail for the control's own inconsistency rather than for the thing it tests, so the
    # prefixes follow the hashes they stand for.
    for old_prefix, new_prefix in rewritten_prefixes.items():
        agreeing_text = agreeing_text.replace(f"`{old_prefix}…`", f"`{new_prefix}…`")
    agreeing_notice = tmp_path / "NOTICE-agreeing"
    agreeing_notice.write_text(agreeing_text, encoding="utf-8")
    agreed_synthetic = _run_replaceability_tool(
        "--check-artefacts", str(artefacts), notice=agreeing_notice
    )
    assert agreed_synthetic.returncode == 0, (
        f"a record whose hashes are the hashes of the files written here was rejected "
        f"({agreed_synthetic.returncode}):\n"
        f"{agreed_synthetic.stdout}\n{agreed_synthetic.stderr}"
    )
    assert "each hashed to the sha256" in agreed_synthetic.stdout, (
        "the agreement arm passed without reporting what it hashed:\n" + agreed_synthetic.stdout
    )

    # The installer rows have the same shape: each states a sha256 for a 124-megabyte
    # build product. A wrong digit in one of them is invisible to every other check in
    # this file, so the comparison is shown able to fail on files written here — named the
    # way the build names them, so the reader finds them and then disagrees with the hash.
    fake_installer_root = tmp_path / "installers"
    fake_installer_root.mkdir()
    for index in range(REPLACEABILITY_INSTALLER_ROWS):
        build_directory = fake_installer_root / f"dist-{index}"
        build_directory.mkdir()
        (build_directory / "LabCairn Setup 0.0.0.exe").write_bytes(
            bytes([48 + index]) * (1024 * (index + 1))
        )
    installer_mismatched = _run_replaceability_tool("--check-installers", str(fake_installer_root))
    assert installer_mismatched.returncode == 1, (
        f"four installer files that hash to none of the recorded values produced exit "
        f"{installer_mismatched.returncode}; the installer comparison is not comparing:\n"
        f"{installer_mismatched.stdout}\n{installer_mismatched.stderr}"
    )
    for row in watch.installer_rows(notice_text):
        assert row.label in installer_mismatched.stderr, (
            f"the installer comparison reddened without naming the row {row.label!r}:\n"
            f"{installer_mismatched.stderr}"
        )

    # Where the real artefacts are on hand, the same flag has to agree with the record.
    raw = os.environ.get("LABCAIRN_REPLACEABILITY_DIR", "").strip()
    directory = Path(raw) if raw else None
    if directory is None or not directory.is_dir():
        pytest.skip(
            "LABCAIRN_REPLACEABILITY_DIR does not name a directory holding the modified "
            "plug-ins and observation files §2.5.1 hashes, so the recorded sha256 values "
            "were not measured against the artefacts in this run; the controls above ran "
            "regardless"
        )
    agreed = _run_replaceability_tool("--check-artefacts", str(directory))
    assert agreed.returncode == 0, (
        f"the artefacts in {directory} did not hash to what §2.5.1 records:\n"
        f"{agreed.stdout}\n{agreed.stderr}"
    )
    assert "each hashed to the sha256" in agreed.stdout, (
        f"the byte check passed without reporting what it hashed:\n{agreed.stdout}"
    )

    # The installers themselves, where the build products are on hand.
    installer_raw = os.environ.get("LABCAIRN_REPLACEABILITY_INSTALLERS", "").strip()
    installer_root = Path(installer_raw) if installer_raw else None
    if installer_root is None or not installer_root.is_dir():
        pytest.skip(
            "LABCAIRN_REPLACEABILITY_INSTALLERS does not name a directory holding the "
            "installer build products \u00a72.5.1's table hashes, so those sha256 values were "
            "not measured against installers in this run; the controls above ran regardless"
        )
    installers_agreed = _run_replaceability_tool("--check-installers", str(installer_root))
    assert installers_agreed.returncode == 0, (
        f"the installers under {installer_root} did not hash to what \u00a72.5.1's table "
        f"records:\n{installers_agreed.stdout}\n{installers_agreed.stderr}"
    )
    assert "each hashed to the sha256 its table row states" in installers_agreed.stdout, (
        f"the installer check passed without reporting what it hashed:\n{installers_agreed.stdout}"
    )
