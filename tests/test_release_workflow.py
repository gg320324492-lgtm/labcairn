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
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import sys
import tarfile
import zipfile
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
    (root / "NOTICE").write_text("A notice.\n", encoding="utf-8")

    planted: list[str] = []
    for name in fonts:
        path = root / "fonts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a font's bytes")
        planted.append(f"fonts/{name}")

    _git(root, "init", "--quiet")
    _git(root, "add", "--", "src/labcairn/__init__.py", "NOTICE", *planted)
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

    members = ["NOTICE", "src/labcairn/__init__.py", *planted]
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
        "licenses/LICENSE.PENDING.md",
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
    """The evidence a paid run leaves goes to the runner's temp, not the tree.

    Every temp root in this repository lives outside the working tree for one
    reason: a file a run wrote into the checkout can be read back by a later
    step and presented as an artefact of the build.
    """
    document = _smoke_document(repo_root)
    job = (document.get("jobs") or {}).get(PROVIDER_SMOKE_JOB) or {}
    env = job.get("env") or {}
    record = str(env.get("LABCAIRN_PROVIDER_SMOKE_RECORD", ""))
    assert record.startswith("${{ runner.temp }}"), (
        f"the probe record goes to {record!r}; a paid run must not write into the checkout"
    )
