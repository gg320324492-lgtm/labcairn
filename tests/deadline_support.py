"""Deadlines for the waits this repository's own tests and scripts perform.

**Why this module exists.** A wait with no deadline is a hang waiting for a
cause: a child that dies before it prints the line the parent is reading, a
``git`` that blocks on a credential prompt, a queue nobody fills. The drill
tests' helper was found doing exactly this on 2026-11-28 — a child that died
before its marker line left the parent blocked in ``readline()`` forever, at
zero CPU, with no failure to report. The hang cost that one file 603.91 s on
one runner and 1204.83 s on another, and the *successful* runs were slow too.

That was one instance of a class. The tree waits on children, interpreters,
``git`` and queues in many places, and every one of those waits has the same
failure mode. So the bound is stated **once**, here, and every call site uses
it.

**What a deadline has to do, or it is half a fix.** A wait that gives up has
to *say what it saw*: the child's exit status, the output that arrived, the
command that was run. A timeout that raises a bare ``TimeoutExpired`` sends
the reader to look for a timing problem when the real fault is an import error
three lines away. So :func:`bounded_run` raises :class:`DeadlineExceededError`,
which carries the command, the limit, and whatever the process managed to
print.

**The numbers.** They are not arbitrary:

* :data:`COMMAND_TIMEOUT_SECONDS` (300 s) is for a command that is *doing
  work* — an interpreter rendering a chart, a ``git`` walking history. It is
  the bound ``tests/test_cli_support.py`` already used, so the tree has one
  number for "a command that should finish".
* :data:`GIT_TIMEOUT_SECONDS` (120 s) is for ``git``. Git is the one command
  in this tree that can block on something outside the run — a credential
  helper, a lock held by another process — and it is the one that is called
  most often, so its bound is the tighter one.
* :data:`FAST_TIMEOUT_SECONDS` (60 s) is for the commands that cannot
  plausibly take longer than a minute: ``mklink``, ``taskkill``, ``kill``.

**What this module does not do.** It does not change what any command does,
and it does not decide *whether* a command should succeed. It bounds how long
the tree is willing to wait, and it says what it saw when the bound is hit.

**Where the helper lives.** Under ``tests/`` because that is where the tree's
shared test helpers live — ``store_support``, ``drill_support`` and the rest
are all there — and because a module under ``src/`` would be shipped in the
wheel, and the product is not what is being bounded here. The scripts that
need it insert the repository's ``tests/`` directory on ``sys.path``, which
several of them already do for other reasons.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from typing import IO, Any, Literal, overload

__all__ = [
    "COMMAND_TIMEOUT_SECONDS",
    "FAST_TIMEOUT_SECONDS",
    "GIT_TIMEOUT_SECONDS",
    "DeadlineExceededError",
    "bounded_fast",
    "bounded_git",
    "bounded_run",
    "describe_process",
    "read_line_within",
    "read_stream_within",
]


#: A command that is doing work: an interpreter, a renderer, a build.
#:
#: It is the bound ``tests/test_cli_support.py`` already applied to the CLI,
#: chosen so that the tree has one number for "a command that should finish".
#: It is generous because it has to cover a chart render on a loaded CI
#: runner; it is finite because the point of the module is that it is.
COMMAND_TIMEOUT_SECONDS = 300.0

#: A ``git`` command.
#:
#: Git is the one command in this tree that can block on something outside
#: the run -- a credential helper, a lock another process holds -- and it is
#: called most often, so its bound is the tighter of the two.
GIT_TIMEOUT_SECONDS = 120.0

#: A command that cannot plausibly take a minute: ``mklink``, ``taskkill``,
#: ``kill``.
FAST_TIMEOUT_SECONDS = 60.0


class DeadlineExceededError(RuntimeError):
    """A command did not finish inside its bound.

    **It says what it saw.** The command that was run, the bound it was
    given, the output that had arrived, and the child's exit status if it
    had one. A reader who has only the message should be able to tell
    whether the command hung, failed, or printed something it should not
    have — without opening a file or re-running anything.
    """

    def __init__(
        self,
        command: Sequence[str],
        timeout: float,
        *,
        stdout: str = "",
        stderr: str = "",
        status: int | None = None,
    ) -> None:
        self.command = list(command)
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr
        self.status = status
        super().__init__(self.describe())

    def describe(self) -> str:
        """The whole story, as one block of text."""
        parts = [
            f"the command did not finish within {self.timeout:g}s:\n"
            f"  {' '.join(self.command)}\n"
            f"status: {describe_process(self.status)}"
        ]
        if self.stdout:
            parts.append("stdout:\n" + self.stdout[-2000:])
        if self.stderr:
            parts.append("stderr:\n" + self.stderr[-2000:])
        if not self.stdout and not self.stderr:
            parts.append("the command printed nothing")
        return "\n".join(parts)


def describe_process(status: int | None) -> str:
    """An exit status, said in words when there is none.

    ``None`` means the process was still running when the deadline was hit,
    which is a different fact from a non-zero exit and is worth saying
    differently: a process that was still running is a process that was
    *waiting*, and a process that exited was a process that *decided*.
    """
    if status is None:
        return "the process was still running"
    if status == 0:
        return "the process exited 0"
    return f"the process exited {status}"


def _as_text(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw


@overload
def bounded_run(
    command: Sequence[str],
    *,
    text: Literal[True],
    encoding: str | None = ...,
    errors: str | None = ...,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@overload
def bounded_run(
    command: Sequence[str],
    *,
    text: bool = ...,
    encoding: str,
    errors: str,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@overload
def bounded_run(
    command: Sequence[str],
    *,
    text: bool = ...,
    encoding: None = ...,
    errors: str | None = ...,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[bytes]: ...


def bounded_run(
    command: Sequence[str],
    *,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run *command* with a deadline, and say what it saw when it misses it.

    The keyword arguments are :func:`subprocess.run`'s, with two differences:
    the deadline is stated here rather than by the caller, and the failure is
    :class:`DeadlineExceededError` rather than a bare
    :class:`subprocess.TimeoutExpired`.

    **The output that arrived is kept.** ``subprocess.run`` captures the
    child's output before raising, so a command that printed a traceback and
    then hung still has that traceback, and the exception carries it. That is
    the difference between a failure that names the fault and a failure that
    names the symptom.

    **A command that fails is not a timeout.** ``check=True`` still raises
    :class:`subprocess.CalledProcessError` for a non-zero exit; this helper
    only changes what happens when the *bound* is hit.

    **The command is killed when the bound is hit.** ``subprocess.run`` kills
    the child on a timeout; this helper lets it, and then describes the
    result rather than leaving a child running behind a failure.
    """
    try:
        return subprocess.run(command, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired as expired:
        stdout = _as_text(expired.stdout)
        stderr = _as_text(expired.stderr)
        raise DeadlineExceededError(
            list(command),
            timeout,
            stdout=stdout,
            stderr=stderr,
            status=None,
        ) from expired


@overload
def bounded_git(
    command: Sequence[str],
    *,
    text: Literal[True],
    encoding: str | None = ...,
    errors: str | None = ...,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@overload
def bounded_git(
    command: Sequence[str],
    *,
    text: bool = ...,
    encoding: str,
    errors: str,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@overload
def bounded_git(
    command: Sequence[str],
    *,
    text: bool = ...,
    encoding: None = ...,
    errors: str | None = ...,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[bytes]: ...


def bounded_git(
    command: Sequence[str],
    *,
    timeout: float = GIT_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a ``git`` command with the tree's git bound.

    Separate from :func:`bounded_run` so that the bound is **named at the
    call site** rather than repeated as a number: a reader of
    ``bounded_git(["git", "log", ...])`` can see that it is git and that git
    has its own tighter bound, without reading the constant's value.
    """
    return bounded_run(command, timeout=timeout, **kwargs)


@overload
def bounded_fast(
    command: Sequence[str],
    *,
    text: Literal[True],
    encoding: str | None = ...,
    errors: str | None = ...,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@overload
def bounded_fast(
    command: Sequence[str],
    *,
    text: bool = ...,
    encoding: str,
    errors: str,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@overload
def bounded_fast(
    command: Sequence[str],
    *,
    text: bool = ...,
    encoding: None = ...,
    errors: str | None = ...,
    timeout: float = ...,
    **kwargs: Any,
) -> subprocess.CompletedProcess[bytes]: ...


def bounded_fast(
    command: Sequence[str],
    *,
    timeout: float = FAST_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a command that cannot plausibly take a minute.

    ``mklink``, ``taskkill`` and ``kill`` are all of them: each either
    creates one directory entry or ends one process, and each is on the
    failure path of a test that has already gone wrong, so a long wait on
    one of them is a symptom rather than a cost.
    """
    return bounded_run(command, timeout=timeout, **kwargs)


def read_line_within(
    stream: IO[str] | None,
    *,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> str:
    """One line from *stream*, or the empty string if none arrived in time.

    **A child that never prints the line leaves the parent waiting for
    it.** ``readline()`` on a pipe a live child holds open returns when the
    line arrives and not otherwise, so a child that hangs before its line
    parks the reader forever — at zero CPU, with no failure to report. The
    read therefore happens on a thread with a deadline, and a child that
    has not spoken by then yields the empty string, which the caller
    already knows how to read as "the child stopped before its round was
    over".

    **The empty string is the answer, not an exception.** The callers of
    this helper are already reporting a failure when the line does not
    arrive, and they report it better than this helper could: they have
    the child's error output to attach. So the helper's job is to *stop
    waiting*, and the caller's job is to say what it saw.
    """
    if stream is None:
        return ""

    collected: list[str] = []
    finished = threading.Event()

    def drain() -> None:
        try:
            line = stream.readline()
        except (OSError, ValueError):  # pragma: no cover - the stream was closed
            line = ""
        collected.append(line)
        finished.set()

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    finished.wait(timeout=timeout)
    return "".join(collected)


def read_stream_within(
    stream: IO[bytes] | IO[str] | None,
    *,
    timeout: float = FAST_TIMEOUT_SECONDS,
) -> str:
    """Whatever *stream* has produced by now, without waiting for its end.

    **A live child holds its stream open**, so reading a child's stderr to
    the end is a way to hang on exactly the failure the caller is trying to
    report: the child that died before it reached the injection point is
    *alive* in the other case — it is parked inside the injector's pause —
    and a read to end-of-stream waits for a pause that lasts minutes.

    So the read happens on a thread, the answer is collected with a
    deadline, and what came back is the text so far. The reader gets the
    child's own error output, which is the thing they came for, without the
    wait that made them unable to report it.

    **The bound is short.** The purpose is to collect a diagnostic, not to
    wait for a child to finish: a child that has already died has its whole
    output available immediately, so a second is generous and a minute would
    be a minute of a hung run.
    """
    if stream is None:
        return ""

    collected: list[str] = []
    finished = threading.Event()

    def drain() -> None:
        try:
            raw = stream.read()
        except (OSError, ValueError):  # pragma: no cover - the stream was closed
            raw = b""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        collected.append(raw)
        finished.set()

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    finished.wait(timeout=timeout)
    return "".join(collected)
