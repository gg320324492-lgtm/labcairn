"""The two catches the crash fix added, watched one at a time.

**What is watched here is the catch, and not the refusal.** The refusals the
CLI renders when a source root is missing, is a file, is outside the
workspace, or is a name this build cannot speak are watched in
``tests/test_cli_workspace_refusals.py``, and those witnesses watch the
*refusals* — the sentences the CLI writes when it refuses for a reason of its
own. **Nothing watched the two ``except PathRefusedError`` clauses the crash
fix (F54) added**: the one in :func:`labcairn.cli.workspace.bind_workspace`,
and the one in the CLI's own refusal handler. They are load-bearing — with
them the layer's refusal is a refusal, and without them it is a traceback —
and a fix that nothing watches is a fix a later change can take away without
anyone noticing.

**The refusal is injected where the layer raises it.** The layer's own root
binder, :func:`labcairn.security.paths.bind_root`, is where a root that
cannot be canonicalised is turned into a
:class:`~labcairn.security.paths.PathRefusedError`. This file makes that
binder refuse, with the layer's own exception and the layer's own reason
code, and asks the CLI what it does with the refusal that arrives. The
injection is a **substitution and not a race**: nothing here depends on a
directory vanishing at the right moment, or on what this machine's filesystem
happens to do, so the same measurement is the same measurement tomorrow.

**The two catches are told apart by the sentence they produce.** A refusal
that reaches :func:`labcairn.cli.workspace.bind_workspace` is answered with
*"the workspace at &lt;root&gt; could not be bound: …"*. A refusal that
reaches the CLI's own handler — one that did not pass through
``bind_workspace`` — is answered with *"the workspace could not be bound:
…"*. The phrase *"at &lt;root&gt;"* is the difference, and **each witness
below is written so that it fails when its own catch is removed**:

* the first drives a command whose refusal passes through
  ``bind_workspace``, and asserts the phrase that only that catch's answer
  has — so it is green while the CLI's own handler is broken, and red once
  ``bind_workspace`` stops catching the layer's refusal;
* the second drives a command whose refusal reaches the CLI's handler
  **without** passing through ``bind_workspace``, and asserts that it is
  rendered as a refusal carrying the exit code a refusal carries — so it is
  green while ``bind_workspace`` is broken, and red once the CLI's own
  handler stops catching the layer's refusal.

**Neither is green when both are broken**, because then the layer's refusal
escapes the command as a traceback: exit code 1, and the layer's exception
in the operator's face. That is the shape F54 was raised for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from labcairn.cli.commands import EXIT_REFUSED, app
from labcairn.cli.workspace import locate
from labcairn.security.paths import (
    AllowedRoot,
    PathRefusedError,
    PathRejection,
    RootKind,
)
from labcairn.workspace import roots as workspace_roots

pytestmark = pytest.mark.negative

#: The reason the CLI gives for a workspace it cannot use.
#:
#: The CLI's own vocabulary, from :data:`labcairn.cli.models.CLI_REFUSAL_WORKSPACE_UNUSABLE`.
#: Both refusals in this file are that one: the layer's refusal reached the
#: CLI, and the CLI could not use the workspace it names.
WORKSPACE_UNUSABLE = "workspace_unusable"

#: The phrase :func:`labcairn.cli.workspace.bind_workspace` puts in its answer,
#: and the phrase it does not.
#:
#: The two are the difference between the two catches, and the whole of what
#: this file measures. The first names the workspace root the refusal was
#: about; the second does not, because the refusal reached the CLI's handler
#: without passing through the workspace module.
NAMED_ROOT = "the workspace at {root} could not be bound: "
UNNAMED_ROOT = "the workspace could not be bound: "

#: The reason code the layer's own refusal carries.
#:
#: :data:`labcairn.security.paths.PathRejection.CANONICALISATION_FAILED` — the
#: code :func:`labcairn.security.paths.bind_root` raises when
#: ``Path.resolve(strict=True)`` fails. It is the layer's own vocabulary, and
#: the witness asserts it survived the journey unchanged.
CANONICALISATION_FAILED = "canonicalisation_failed"


@dataclass(frozen=True, slots=True)
class CliResult:
    """What one run of the CLI produced, in this process."""

    returncode: int
    stdout: str
    stderr: str
    exception: BaseException | None


def _invoke(*args: str) -> CliResult:
    """The CLI, run in this process.

    The runner is used rather than the console script because the point of
    these witnesses is **the layer's refusal arriving at the CLI**, and the
    refusal is injected by substitution — which needs the command and the
    injection to be in the same process.
    """
    outcome = CliRunner().invoke(app, list(args))
    return CliResult(
        outcome.exit_code,
        outcome.stdout,
        outcome.stderr,
        outcome.exception,
    )


def _the_layer_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the layer's own root binder refuse.

    The refusal is the layer's: :class:`PathRefusedError`, carrying the
    layer's own reason code, with the detail in the layer's own shape — the
    wording :func:`labcairn.security.paths.bind_root` itself uses when
    ``Path.resolve(strict=True)`` fails.

    **Every root is refused, and the first one is the workspace's own**, so
    the refusal happens where the layer binds the root the operator selected.
    The binder is substituted in the module that calls it, because that is
    where the layer binds its roots; the exception it raises is the layer's
    own, raised with the layer's own reason.
    """

    def refusing_bind_root(root_id: str, path: Path, kind: RootKind) -> AllowedRoot:
        raise PathRefusedError(
            PathRejection.CANONICALISATION_FAILED,
            f"root {root_id!r} at {path} could not be resolved strictly: "
            "the directory could not be canonicalised",
        )

    monkeypatch.setattr(workspace_roots, "bind_root", refusing_bind_root)


def _the_refusal(result: CliResult) -> dict[str, Any]:
    """The refusal the CLI printed, checked to be one.

    **The escape is checked first.** A layer refusal that left the command
    is the crash F54 was raised for, and it is checked by its type rather
    than by its exit code alone: the exit code a crash carries is 1, and a
    witness that only watched the exit code would be satisfied by any other
    failure that happened to carry it.

    The exit code and the reason are asserted before the message is read, so
    a test that fails says *which* of them went wrong.
    """
    assert not isinstance(result.exception, PathRefusedError), (
        f"the layer's refusal escaped the command as a crash: {result.exception!r}"
    )
    assert result.returncode == EXIT_REFUSED, (
        f"expected the refusal exit code {EXIT_REFUSED}, got {result.returncode}; "
        f"stdout was {result.stdout!r}, stderr was {result.stderr!r}"
    )
    payload: dict[str, Any] = json.loads(result.stdout)
    assert payload["reason"] == WORKSPACE_UNUSABLE, payload
    return payload


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace the CLI itself made."""
    root = tmp_path / "workspace"
    result = _invoke("--workspace", str(root), "init")
    assert result.returncode == 0, (
        f"init failed: {result.returncode}; stdout was {result.stdout!r}, "
        f"stderr was {result.stderr!r}"
    )
    return root


@pytest.fixture
def task_workspace(workspace: Path) -> Path:
    """A workspace the CLI itself made, holding one task.

    The task is made **before** any refusal is injected, because making a
    task binds the workspace too, and a witness that injected its refusal
    into the making of the workspace would be measuring its own fixture.
    """
    result = _invoke(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "A task to report on",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, (
        f"task create failed: {result.returncode}; stdout was {result.stdout!r}, "
        f"stderr was {result.stderr!r}"
    )
    return workspace


def test_a_refusal_the_workspace_binds_is_answered_with_the_root_named(
    task_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The layer's refusal reaches the workspace module, and is answered there.

    **This is the catch in** :func:`labcairn.cli.workspace.bind_workspace`.
    The layer refuses to bind the workspace; the workspace module turns that
    refusal into a refusal of its own, **naming the root the refusal was
    about**, and the CLI renders it with the exit code a refusal carries.

    **The phrase is the witness.** *"the workspace at &lt;root&gt; could not
    be bound"* is what ``bind_workspace``'s answer says, and it is not what
    the CLI's own handler says — that one leaves the root out. So a
    ``bind_workspace`` that stopped catching the layer's refusal would let
    the refusal through to the CLI's handler, the phrase would be lost, and
    **this witness would go red while the CLI's own handler was broken
    would not affect it at all.**
    """
    _the_layer_refuses(monkeypatch)

    result = _invoke("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _the_refusal(result)
    message = payload["message"]
    root = locate(task_workspace).root
    assert message.startswith(NAMED_ROOT.format(root=root)), message
    assert f"{CANONICALISATION_FAILED}: " in message, message


def test_a_refusal_that_skips_the_workspace_is_answered_by_the_cli(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The layer's refusal reaches the CLI's own handler, and is answered there.

    **This is the catch in the CLI's refusal handler.** The refusal here is
    raised while a task is being made, and the task's own maker catches the
    workspace's errors but not the layer's path refusal — so the refusal
    travels the rest of the way **without passing through
    :func:`labcairn.cli.workspace.bind_workspace`**, and arrives at the
    CLI's handler, which must turn it into a refusal rather than let it out
    as a traceback.

    **This is the second level, and the two levels are told apart by their
    sentences.** This catch's answer leaves the root out — *"the workspace
    could not be bound"* — where the workspace module's answer names it. So
    a CLI handler that stopped catching the layer's refusal would let the
    layer's exception escape the command, the exit code would become the
    crash's 1, and **this witness would go red** — while the first witness
    stayed green, because on that path the refusal never reaches the
    handler.
    """
    _the_layer_refuses(monkeypatch)

    result = _invoke(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "A task that never gets made",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )

    payload = _the_refusal(result)
    message = payload["message"]
    assert message.startswith(UNNAMED_ROOT), message
    assert f"{CANONICALISATION_FAILED}: " in message, message
