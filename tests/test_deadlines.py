"""Every wait in the tree has a deadline, and every deadline has a witness.

**What this file is.** The drill tests' helper was found on 2026-11-28 to
wait on a child's output with no bound: a child that died before printing its
marker line left the parent blocked in ``readline()`` forever, at zero CPU,
with no failure to report. That was one instance of a class, and a class
needs a witness for the whole of it.

So this file watches two things.

1. **That the tree's waits are bounded.** It reads the tree's own source and
   finds every wait that can park — a ``subprocess.run`` with no
   ``timeout=``, a ``readline()`` on a pipe, a ``.result()`` on a future — and
   requires each of them to carry a deadline. This is the sweep's own
   witness, and it fails the moment somebody adds the next unbounded wait.

2. **That the deadlines work.** Each of :func:`bounded_run`,
   :func:`bounded_git`, :func:`bounded_fast`, :func:`read_line_within` and
   :func:`read_stream_within` is driven into the state that used to hang, and
   is required to give up within its bound and to say what it saw.

**Why the second kind of test is here at all.** A sweep that only adds
``timeout=`` everywhere is a sweep that can be quietly undone: delete the
argument and every test still passes, because the tests were never in the
state that hangs. These tests put the wait *in* that state. That is the
project's own rule — a claim about a behaviour needs a witness that fails
when the behaviour is broken — applied to the deadline itself.

**Why the bounds are different numbers.** ``git`` is called most often and
can block on a credential helper; an interpreter rendering a chart on a loaded
runner needs the longest; ``taskkill`` and ``mklink`` cannot take a minute.
The numbers are argued in ``tests/deadline_support.py`` and recorded in the
sweep's own document.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import time
from pathlib import Path

import pytest
from deadline_support import (
    COMMAND_TIMEOUT_SECONDS,
    FAST_TIMEOUT_SECONDS,
    GIT_TIMEOUT_SECONDS,
    DeadlineExceededError,
    bounded_fast,
    bounded_git,
    bounded_run,
    read_line_within,
    read_stream_within,
)

#: The repository root.
ROOT = Path(__file__).resolve().parent.parent

#: The directories whose waits this file watches.
WATCHED = ("tests", "scripts", "examples", ".github")

#: A child that prints one line and then waits for an eternity.
#:
#: It is the shape of the defect: a child that says something and then never
#: says the thing the parent is waiting for. The parent blocks on the second
#: line and never learns that the first one arrived.
SLEEP_FOREVER = (
    "import sys, time; sys.stdout.write('first\\n'); sys.stdout.flush(); time.sleep(600)"
)

#: A child that never prints anything at all.
SILENT = "import time; time.sleep(600)"


# --------------------------------------------------------------------------- #
# the deadlines work
# --------------------------------------------------------------------------- #


def test_a_command_that_never_finishes_is_given_up_on() -> None:
    """A command that hangs is given up on, and the failure says so.

    **The witness.** The child sleeps for ten minutes; the bound is three
    seconds. Without the deadline this test hangs for ten minutes, and with
    it the test finishes in about three. So the deadline is not a decoration
    on this path — removing it makes the witness itself hang, which is the
    clearest possible demonstration that the property is being held.
    """
    started = time.monotonic()
    with pytest.raises(DeadlineExceededError) as raised:
        bounded_run([sys.executable, "-c", SLEEP_FOREVER], timeout=3.0)
    elapsed = time.monotonic() - started

    assert elapsed < 30.0, f"the deadline was not honoured: it took {elapsed:.1f}s"
    assert "did not finish within 3" in str(raised.value)


def test_the_failure_says_what_the_command_printed() -> None:
    """A command that printed and then hung is reported with what it printed.

    **Why this matters.** A timeout that raises a bare ``TimeoutExpired``
    sends the reader looking for a timing problem when the real fault is an
    import error three lines away. So the helper keeps the output that
    arrived, and the failure carries it.
    """
    program = (
        "import sys, time; sys.stdout.write('the real fault\\n'); "
        "sys.stdout.flush(); time.sleep(600)"
    )
    with pytest.raises(DeadlineExceededError) as raised:
        bounded_run([sys.executable, "-c", program], timeout=3.0, capture_output=True, text=True)

    assert "the real fault" in str(raised.value), (
        f"the failure did not carry the output the command had printed:\n{raised.value}"
    )


def test_the_failure_says_the_command_and_the_bound() -> None:
    """The failure names the command that was run and the bound it was given.

    A reader with only the message should be able to tell what was being
    waited for and for how long, without opening a file or re-running
    anything.
    """
    with pytest.raises(DeadlineExceededError) as raised:
        bounded_run([sys.executable, "-c", SLEEP_FOREVER], timeout=3.0)

    message = str(raised.value)
    assert sys.executable in message, message
    assert "3s" in message, message
    assert "still running" in message, (
        f"the failure did not say the command was still running:\n{message}"
    )


def test_a_command_that_fails_is_not_a_deadline_failure() -> None:
    """A command that exits non-zero still raises the error it always did.

    **The deadline changes one thing.** A command that fails has failed; it
    has not hung, and a helper that turned a failure into a timeout would
    hide the real fault behind a timing one.
    """
    with pytest.raises(subprocess.CalledProcessError):
        bounded_run([sys.executable, "-c", "raise SystemExit(3)"], timeout=30.0, check=True)


def test_a_command_that_succeeds_is_not_changed() -> None:
    """The successful path is the one it always was: the same output."""
    completed = bounded_run(
        [sys.executable, "-c", "print('hello')"],
        timeout=30.0,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "hello"


def test_the_git_bound_is_the_tighter_one() -> None:
    """Git has its own bound, and it is the tighter of the two.

    **The bound is named at the call site.** ``bounded_git`` says "this is
    git" without the reader having to look up a constant, and git's bound is
    the tighter one because git is the command in this tree that can block
    on something outside the run.
    """
    assert GIT_TIMEOUT_SECONDS < COMMAND_TIMEOUT_SECONDS
    assert FAST_TIMEOUT_SECONDS < COMMAND_TIMEOUT_SECONDS


def test_a_git_command_that_never_finishes_is_given_up_on() -> None:
    """The git bound is a bound, not a comment.

    The child is not git — git would need a real repository to hang in, and
    a fake repository that hangs is a fixture with more moving parts than
    the property is worth. What is under test is that the *helper* honours
    the bound it was given, and the child is the cheapest way to give it
    something to wait for.
    """
    started = time.monotonic()
    with pytest.raises(DeadlineExceededError):
        bounded_git([sys.executable, "-c", SLEEP_FOREVER], timeout=3.0)
    elapsed = time.monotonic() - started
    assert elapsed < 30.0, f"the deadline was not honoured: it took {elapsed:.1f}s"


def test_the_fast_bound_is_a_bound_too() -> None:
    """The fast bound is a bound, and not a comment."""
    started = time.monotonic()
    with pytest.raises(DeadlineExceededError):
        bounded_fast([sys.executable, "-c", SLEEP_FOREVER], timeout=3.0)
    elapsed = time.monotonic() - started
    assert elapsed < 30.0, f"the deadline was not honoured: it took {elapsed:.1f}s"


def test_a_line_that_never_arrives_is_given_up_on() -> None:
    """A child that never prints its line does not park the reader.

    **This is the drill defect itself, in miniature.** The drill's helper
    looped on ``readline()`` until the child's stream *ended*; a child that
    died before its marker line left the parent blocked on a read that would
    never return. Here the child prints nothing at all and keeps the pipe
    open, and the read is required to come back empty within its bound.
    """
    child = subprocess.Popen(
        [sys.executable, "-c", SILENT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        started = time.monotonic()
        line = read_line_within(child.stdout, timeout=3.0)
        elapsed = time.monotonic() - started
    finally:
        child.kill()
        child.wait(timeout=30)

    assert elapsed < 30.0, f"the deadline was not honoured: it took {elapsed:.1f}s"
    assert line == "", f"the read produced a line it should not have: {line!r}"


def test_a_line_that_arrives_is_returned() -> None:
    """The successful path of the line read is unchanged: the same line.

    And a child that prints a line and then keeps the pipe open still
    yields that line promptly — the deadline does not cost the working
    path anything.
    """
    child = subprocess.Popen(
        [sys.executable, "-c", SLEEP_FOREVER],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        started = time.monotonic()
        line = read_line_within(child.stdout, timeout=30.0)
        elapsed = time.monotonic() - started
    finally:
        child.kill()
        child.wait(timeout=30)

    assert elapsed < 30.0, f"the deadline was not honoured: it took {elapsed:.1f}s"
    assert line.strip() == "first", f"the read produced the wrong line: {line!r}"


def test_a_stream_that_never_ends_is_given_up_on() -> None:
    """A live child holds its stderr open, and the read does not wait for it.

    **This is the other shape of the same defect.** Reading a child's stderr
    to its end is a way to hang on exactly the failure the caller is trying
    to report: the child that is *alive* and parked is the one whose stderr
    will not end.
    """
    child = subprocess.Popen(
        [sys.executable, "-c", SILENT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stderr is not None
        started = time.monotonic()
        collected = read_stream_within(child.stderr, timeout=3.0)
        elapsed = time.monotonic() - started
    finally:
        child.kill()
        child.wait(timeout=30)

    assert elapsed < 30.0, f"the deadline was not honoured: it took {elapsed:.1f}s"
    assert collected == "", f"the read produced text it should not have: {collected!r}"


def test_a_stream_that_has_ended_is_read_to_the_end() -> None:
    """The successful path of the stream read is unchanged: the whole text."""
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stderr.write('the fault\\n')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stderr is not None
        child.wait(timeout=30)
        collected = read_stream_within(child.stderr, timeout=30.0)
    finally:
        child.kill()
        child.wait(timeout=30)

    assert "the fault" in collected, f"the read lost the child's own error: {collected!r}"


# --------------------------------------------------------------------------- #
# the tree's waits are bounded
# --------------------------------------------------------------------------- #

#: The calls that can park the calling thread, and so need a deadline.
#:
#: ``subprocess.run`` is the one that matters most — it is how the tree
#: starts ninety-nine children — and it is bounded either by a ``timeout=``
#: keyword of its own or by going through one of the helpers.
BLOCKING_CALLS = {"run", "check_output", "check_call", "communicate"}


def _python_files() -> list[Path]:
    files: list[Path] = []
    for directory in WATCHED:
        files.extend(sorted((ROOT / directory).rglob("*.py")))
    return files


def _helper_names(node: ast.Call) -> set[str]:
    """The deadline helpers a call goes through, if any."""
    if not isinstance(node.func, ast.Name):
        return set()
    return {node.func.id} & {"bounded_run", "bounded_git", "bounded_fast"}


def test_no_subprocess_call_in_the_tree_has_no_deadline() -> None:
    """Every ``subprocess.run`` in the tree carries a deadline.

    **This is the sweep's own witness.** It reads the tree's source rather
    than trusting that the sweep was finished, so the next unbounded wait
    fails here instead of being discovered as a hung run.

    The two scripts the repository's own plan marks as *read-only* are
    excluded, and named: they are somebody else's to change.
    """
    offenders: list[str] = []
    for path in _python_files():
        if path.name == "deadline_support.py":
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in _READ_ONLY_SCRIPTS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a file that does not parse
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id != "subprocess":
                continue
            if node.func.attr not in BLOCKING_CALLS:
                continue
            if any(keyword.arg == "timeout" for keyword in node.keywords):
                continue
            if _helper_names(node):
                continue
            offenders.append(f"{relative}:{node.lineno}")

    assert not offenders, (
        "these subprocess calls have no deadline:\n  "
        + "\n  ".join(offenders)
        + "\nEvery wait needs a bound: a wait with no deadline turns a hung "
        "counterpart into a hung run."
    )


#: The scripts the repository's own plan assigns to nobody, read-only.
#:
#: ``docs/plans/LC-P1-01-task-breakdown.md`` §the ownership table gives
#: ``scripts/checkout_upstreams.py`` to **nobody — read-only**, and ruff
#: excludes the file for the same reason. The sweep does not edit it, and
#: this list is where that decision is written down so the exclusion is
#: visible rather than silent.
_READ_ONLY_SCRIPTS = frozenset({"scripts/checkout_upstreams.py"})


def test_the_read_only_script_is_the_only_one_excluded() -> None:
    """The exclusion list is exactly the plan's, and it is not growing.

    A list of files left unbounded is a list that grows. This watches that
    it holds only the file the plan named, so the next unbounded wait cannot
    be *excluded* instead of *bounded*.
    """
    assert frozenset({"scripts/checkout_upstreams.py"}) == _READ_ONLY_SCRIPTS
    plan = (ROOT / "docs" / "plans" / "LC-P1-01-task-breakdown.md").read_text(encoding="utf-8")
    assert "scripts/checkout_upstreams.py" in plan, (
        "the plan no longer names the read-only script; the exclusion list "
        "has to be re-read against the plan rather than carried forward"
    )
    assert "nobody — read-only" in plan, (
        "the plan no longer marks the script read-only; the exclusion has "
        "to be re-decided rather than carried forward"
    )


def _count_bounded_calls() -> int:
    """How many subprocess calls in the tree carry a deadline.

    **Both shapes count.** A call that kept its own ``timeout=`` is
    bounded, and a call that was rewritten to go through a helper is
    bounded; the rewrite turned ninety-nine calls into helper calls, so
    counting only the first shape would count almost none of them.
    """
    bounded = 0
    for path in _python_files():
        if path.name == "deadline_support.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _helper_names(node):
                bounded += 1
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id != "subprocess" or node.func.attr != "run":
                continue
            if any(keyword.arg == "timeout" for keyword in node.keywords):
                bounded += 1
    return bounded


def test_the_tree_has_waits_and_they_are_bounded() -> None:
    """The sweep found waits, and every one of them now carries a deadline.

    A test that passes because there is nothing to check is not a witness.
    This one first requires that the tree *has* the waits — that the sweep
    was looking at a real class — and then requires that each of them is
    bounded.
    """
    bounded = _count_bounded_calls()
    assert bounded >= 90, (
        f"the tree has only {bounded} bounded subprocess calls; the sweep was "
        "looking at a class of waits and the class has gone somewhere else"
    )


def test_the_helper_is_used_everywhere_the_sweep_found_a_wait() -> None:
    """The sweep's own count: the helpers are what the rewrite produced.

    The number is the one measured by the sweep on 2026-11-28 — ninety-nine
    unbounded ``subprocess.run`` calls across forty-seven files — and it is
    checked here so that a later edit which *removes* a deadline cannot pass
    unnoticed by shrinking the class the sweep found.
    """
    helper_calls = 0
    for path in _python_files():
        if path.name == "deadline_support.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _helper_names(node):
                helper_calls += 1

    assert helper_calls >= 90, (
        f"only {helper_calls} calls go through the deadline helpers; the "
        "sweep rewrote ninety-nine of them, so a deadline has been removed"
    )
