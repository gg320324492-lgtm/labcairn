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
"""

from __future__ import annotations

import re
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
