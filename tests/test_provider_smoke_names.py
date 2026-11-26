"""The smoke script and the CI job must name the same variables.

**The hole this closes.** ``scripts/provider_smoke.py`` reads its
configuration from the environment, and
``.github/workflows/provider-smoke.yml`` exports that configuration. The
two agreed on the credential's name and **not** on the other three: the
script read ``LABCAIRN_SMOKE_PROTOCOL``, ``LABCAIRN_SMOKE_MODEL`` and
``LABCAIRN_SMOKE_BASE_URL`` while the workflow exported
``LABCAIRN_PROVIDER_SMOKE_PROTOCOL``, ``LABCAIRN_PROVIDER_SMOKE_MODEL``
and ``LABCAIRN_PROVIDER_SMOKE_BASE_URL``.

**Why nothing noticed.** The credential's name always matched, so the
script's one hard requirement was satisfied and the job got as far as
building its settings. From there the protocol fell back to its default
(``openai``) and the model was empty, so the script refused -- and the
refusal named the **script's** spelling of the model variable, which is
not the name the operator had set. On CI the job therefore failed for a
reason that pointed at the wrong variable, and on a developer's machine
the same setting was simply not read.

**What the witness holds.** The two files are read and the names are
compared, both ways: every variable the script reads must be exported by
the workflow, and every variable the workflow exports that the script
reads must be the same name. A rename on either side that is not
mirrored is a red test here rather than a failed paid run.

**Why it is a repository gate and not a script test.** The property is
about two files agreeing, so the witness reads both. It does not call the
provider, send anything, or need a credential: it is a naming
agreement, and the agreement is what the paid run depends on.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

#: This file is a unit-class witness: it reads two files and compares the
#: names they use. It sends nothing and needs no credential, so it runs
#: on every machine and in every shard.
pytestmark = pytest.mark.unit

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: The script that reads the configuration.
SMOKE_SCRIPT: Final = Path("scripts") / "provider_smoke.py"

#: The job that exports it.
SMOKE_WORKFLOW: Final = Path(".github") / "workflows" / "provider-smoke.yml"

#: The variables the script declares it reads. The pattern matches the
#: module's own ``NAME_VAR: Final = "..."`` declarations, so a variable
#: the script stops reading is no longer counted rather than counted and
#: ignored.
_SCRIPT_VAR: Final = re.compile(r'^[A-Z_]+_VAR:\s*Final\s*=\s*"([A-Z0-9_]+)"', re.MULTILINE)

#: The variables the job exports. The pattern matches the job-level
#: ``env:`` block's ``LABCAIRN_...:`` entries.
_WORKFLOW_VAR: Final = re.compile(r"^\s+(LABCAIRN_[A-Z0-9_]+):", re.MULTILINE)

#: The variables the job is **not** required to export.
#:
#: The timeout is optional in the script's own contract — it falls back
#: to a default — so a job that does not set it is correct, not broken.
#: Everything else the script reads is a setting without which the run
#: cannot do what it was asked to do, so the job must export it.
OPTIONAL_IN_THE_JOB: Final = frozenset({"LABCAIRN_PROVIDER_SMOKE_TIMEOUT"})


def _script_variables() -> set[str]:
    """The variables the smoke script reads."""
    text = (REPO_ROOT / SMOKE_SCRIPT).read_text(encoding="utf-8")
    return set(_SCRIPT_VAR.findall(text))


def _workflow_variables() -> set[str]:
    """The variables the CI job exports."""
    text = (REPO_ROOT / SMOKE_WORKFLOW).read_text(encoding="utf-8")
    return set(_WORKFLOW_VAR.findall(text))


def test_the_smoke_script_and_the_ci_job_name_the_same_variables() -> None:
    """Every variable one side names, the other side names the same.

    **The property.** A name the script reads and the job does not
    export is a setting that silently does not apply -- the protocol
    falls back to its default, the model is empty, and the failure names
    a variable the operator never set. A name the job exports and the
    script does not read is a setting that is present and inert.

    Both directions are checked, because either one alone is a hole: the
    credential's name always matched, which is exactly why the other
    three could disagree for so long without a red run.
    """
    script = _script_variables()
    workflow = _workflow_variables()

    assert script, f"the smoke script declares no variables it reads: {SMOKE_SCRIPT}"
    assert workflow, f"the CI job exports no variables: {SMOKE_WORKFLOW}"

    required = script - OPTIONAL_IN_THE_JOB

    only_in_script = sorted(required - workflow)
    assert not only_in_script, (
        "the smoke script reads variables the CI job does not export, so "
        f"those settings never apply on a runner: {only_in_script}"
    )

    only_in_workflow = sorted(workflow - script)
    assert not only_in_workflow, (
        "the CI job exports variables the smoke script does not read, so "
        f"those settings are present and inert: {only_in_workflow}"
    )


def test_the_smoke_script_documents_the_names_it_reads() -> None:
    """The script's own usage text names the variables it reads.

    **Why this is a separate property.** The script's docstring is how
    an operator learns what to set, and it is the one place where a
    spelling can go stale without anything failing: the code reads one
    name and the prose tells the reader to set another. The docstring is
    read and each declared variable must appear in it.
    """
    text = (REPO_ROOT / SMOKE_SCRIPT).read_text(encoding="utf-8")
    docstring = text.split('"""', 2)[1]

    for name in sorted(_script_variables()):
        assert name in docstring, (
            f"the smoke script reads {name} but its usage text does not name "
            "it, so an operator following the text would not set it"
        )


def test_the_ci_job_checks_for_the_variables_the_script_reads() -> None:
    """The job's missing-variable check names the script's variables.

    **Why this matters separately from the export.** The job refuses to
    run when a variable is missing, and it says which. A check that
    names a variable the script does not read would report a setting as
    present-and-required while the script ignored it -- the job would
    fail on a variable the operator had set, pointing at the wrong one.
    """
    text = (REPO_ROOT / SMOKE_WORKFLOW).read_text(encoding="utf-8")

    for name in sorted(_script_variables() - OPTIONAL_IN_THE_JOB):
        assert name in text, (
            f"the CI job never mentions {name}, so its missing-variable "
            "check cannot name the setting the script actually reads"
        )
