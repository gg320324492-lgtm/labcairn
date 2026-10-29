"""Reading pytest's JUnit XML.

**Why JUnit XML and not pytest's own API.** The harness runs each gate class
as a **subprocess** — the protocol's classes are partitions of a test suite,
and a suite that runs inside the suite is a suite that cannot be trusted to
report the outer suite's own result. So the harness needs the inner run's
outcomes as data, and JUnit XML is what pytest writes without a plugin.

**Why not ``pytest-json-report``.** It is a third-party plugin, and a
measurement tool that only works when a plugin is installed measures the
plugin's presence as much as the suite. JUnit XML is in pytest's core.

**The statuses, and the one that matters.** pytest writes four shapes of
non-pass:

* ``<failure>`` — the test ran and failed.
* ``<error>`` — the test could not run to a conclusion.
* ``<skipped type="pytest.skip">`` — the test did not run because
  something skipped it.
* ``<skipped type="pytest.xfail">`` — the test ran and failed **the way it
  was declared it would**.

The last two are both ``<skipped>`` elements, and conflating them is a lie
in one direction or the other. A ``pytest.skip`` is a required test that
did not run, and the protocol's sixth Phase 1 blocker names exactly that.
An ``xfail`` is a different fact: the test ran, and it failed as expected.
The harness keeps them apart, and :data:`tests.evaluation.model.TestOutcome`
says so where it counts them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Final

from .model import ERRORED, FAILED, PASSED, SKIPPED, XFAIL, TestOutcome

#: The ``type`` attribute pytest writes for an expected failure.
XFAIL_TYPE: Final = "pytest.xfail"

#: The longest failure message the report carries. A traceback is not a
#: failure case; the message is what says which case it was.
MESSAGE_LIMIT: Final = 400


def _trim(text: str) -> str:
    """A message short enough to sit in a report row."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= MESSAGE_LIMIT:
        return collapsed
    return collapsed[: MESSAGE_LIMIT - 1] + "…"


def _location(case: ElementTree.Element, classname: str, repo_root: Path | None) -> tuple[str, str]:
    """Where the case lives: its repository-relative file, and its class path.

    **The classname is a module path and then, maybe, a class path — and the
    two are not separable from the string alone.** pytest writes the dotted
    name of the *module*, then the test's class if it has one, and Python's
    grammar lets a module and a class be spelled the same way. The reader used
    to assume there was no class and turned `tests.test_skill_ledger.TestDigests`
    into `tests/test_skill_ledger/TestDigests.py` — a file that is not in the
    tree, so 22 cases entered the index under a name the manifest, the shard
    list and the witness tables do not know, and the metric they witness lost
    its whole denominator without saying so.

    So the split is read off the tree when the tree is named: the longest
    dotted prefix that is an actual file is the module, and what is left is the
    class path. Without a tree to ask, the old guess is all there is, and it is
    stated in the fallback rather than in a promise.
    """
    given = case.get("file")
    if given:
        return given.replace("\\", "/"), ""
    if not classname:
        return "", ""
    parts = classname.split(".")
    if repo_root is not None and len(parts) > 1:
        for cut in range(len(parts), 0, -1):
            candidate = Path(*parts[:cut]).with_suffix(".py")
            if (repo_root / candidate).is_file():
                return candidate.as_posix(), "::".join(parts[cut:])
    if "." in classname:
        return classname.replace(".", "/") + ".py", ""
    return f"tests/{classname}.py", ""


def parse_junit(path: Path, *, repo_root: Path | None = None) -> tuple[TestOutcome, ...]:
    """Every test case in a JUnit XML file, in the order pytest wrote them.

    `repo_root` is the tree the run happened on, and naming it is what lets a
    case in a test **class** be keyed to its file. Reading a report without it
    still works for a suite with no test classes; with one, a class's cases
    land under a path that is not in the tree.

    A file that is not there, or that is not XML, is an error rather than an
    empty result: an empty result would report a class of zero collected
    tests, which is a number that reads as "the class ran and found
    nothing" — and that is exactly the shape of a hole.
    """
    if not path.is_file():
        msg = f"no JUnit XML at {path}; the run produced no report to read"
        raise FileNotFoundError(msg)
    tree = ElementTree.parse(path)
    outcomes: list[TestOutcome] = []
    for case in tree.getroot().iter("testcase"):
        outcomes.append(_outcome_of(case, repo_root))
    return tuple(outcomes)


def _outcome_of(case: ElementTree.Element, repo_root: Path | None = None) -> TestOutcome:
    """One test case's outcome."""
    classname = case.get("classname", "")
    name = case.get("name", "")
    file, class_path = _location(case, classname, repo_root)
    tail = f"{class_path}::{name}" if class_path else name
    node_id = f"{file}::{tail}" if file else tail

    failure = case.find("failure")
    error = case.find("error")
    skipped = case.find("skipped")

    status = PASSED
    message = ""
    if failure is not None:
        status = FAILED
        message = _trim(failure.get("message", "") or (failure.text or ""))
    elif error is not None:
        status = ERRORED
        message = _trim(error.get("message", "") or (error.text or ""))
    elif skipped is not None:
        status = XFAIL if skipped.get("type") == XFAIL_TYPE else SKIPPED
        message = _trim(skipped.get("message", "") or (skipped.text or ""))

    try:
        duration = float(case.get("time", "0") or "0")
    except ValueError:
        duration = 0.0

    return TestOutcome(
        file=file,
        node_id=node_id,
        status=status,
        duration_seconds=duration,
        message=message,
    )
