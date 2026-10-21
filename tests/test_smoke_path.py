"""G4's exit demonstration is run by a test, so it cannot quietly stop working.

Neither ``g1_exit_demo.py`` nor ``g2_exit_demo.py`` is run by CI or by any
test, and the independent review of G3 named that as a hole. This file runs
**G4's** demonstration -- the clean-clone developer launch, and the three
surfaces producing the same versioned report -- as a subprocess, the way a
person runs it, and asserts that it exits zero.

**The exit code is the assertion that matters.** Every claim the
demonstration makes is carried by a ``check()`` that raises rather than warns,
so a non-zero exit means a guard stopped working and a zero exit means every
one of them still holds. A test that only read the output would be testing the
prose.

**And the exit code is asserted from both sides.** A zero exit says every
claim held; on its own it says nothing about whether the run *could* have
failed, and a demonstration that printed its lines and swallowed every failure
would exit zero as readily. So this file also runs the demonstration with a
claim planted false and requires a non-zero exit, and runs it again with a
real defect in the product -- the service answering with bytes that are not
the stored file's bytes -- and requires a non-zero exit there too. **Both
faults are planted from outside:** the demonstration's own source is never
edited, and it has no hook a test could use, because a hook inside the gate's
exit test is a new way for the demonstration to lie about what it did.

The output is asserted too, but for the things the exit code cannot say on
its own: that the eight steps actually ran, that the refusals were refusals
with a reason rather than crashes, that the two surfaces were compared against
**one** store, and that the demonstration said what it did not exercise.

**It runs three times for the whole module, not once per assertion.** The
demonstration walks the whole path -- a workspace, a database, a figure drawn
by matplotlib, four exported forms -- and takes about fifteen seconds, so the
runs are module-scoped: one clean run, one with a claim planted false, and one
with a defect planted in the product. Running it again for every assertion
would multiply that for no extra evidence.

**The hour is this test's to choose.** The service records a grant with its
own clock, so whether the demonstration works is a question about the hour,
and a run at the hour the suite happened to start in cannot answer it. So
the demonstration is run twice more with every clock in it pinned -- the
demonstration's own and the product's -- at two hours eighteen apart, and
the test that does it is the one that says the demonstration means the same
thing at any hour.

**The demonstration's workspace is outside the repository.** That is asserted
here rather than assumed: a workspace inside the checkout would make the run
depend on the tree it is running in, and the demonstration's own claim is that
it is a clean clone.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_developer_launch import run_cli

from labcairn.api.app import create_app
from labcairn.cli.workspace import application_context, locate, read_config
from labcairn.core.ids import TaskId
from labcairn.recovery.resume import STALE_REASON

#: The demonstration, as a person runs it.
DEMO: Path = Path(__file__).parent.parent / "examples" / "g4_exit_demo.py"

#: The eight steps, in the order the acceptance clause names them. A step that
#: stopped running would leave its heading out of the output, so their presence
#: is a fact about what the demonstration did rather than a fact about its
#: prose.
STEPS: tuple[str, ...] = (
    "1. labcairn init",
    "2. labcairn doctor",
    "3. A material, and a task it is bound to",
    "4. The report",
    "5. The three surfaces agree",
    "6. A refresh changes nothing, and repeats nothing",
    "7. An approval cannot be spoofed from another origin",
    "8. The material changes, and the report says so",
)

#: The number of checks the demonstration makes -- a count, not a floor. A
#: claim that was removed shows up here, and so does a claim the
#: demonstration *failed*: a failure it printed and carried on from is
#: counted neither in the lines nor in the summary, so a run that had a claim
#: fail and still said "every check held" would be counted at one fewer. The
#: count is the only thing that would say so.
EXPECTED_CHECKS: int = 58

#: The claim planted false, for the run that has to fail. It is a claim the
#: demonstration makes in its first step, so the planted run stops early and
#: the failure it produces is about the claim and not about the environment.
PLANTED_CLAIM: str = "the database is at the newest migration"

#: The demonstration, driven with a fault planted in it.
#:
#: The program is here rather than in a file of its own because the fault has
#: to be planted *from outside*: the demonstration is loaded as a module, its
#: own ``check()`` is wrapped, and its source is never edited. A seam inside
#: the demonstration would be a new way for the gate's exit test to lie about
#: what it did.
DRIVER: str = """
import importlib.util
import sys

demo_path, mode = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("g4_exit_demo", demo_path)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

if mode == "planted-claim":
    target = sys.argv[3]
    unplanted = demo.check

    def check(label, condition, detail=""):
        if label == target:
            condition = False
        return unplanted(label, condition, detail)

    demo.check = check
elif mode == "altered-bytes":
    import labcairn.api.routes as routes

    unaltered = routes.read_artifact

    def read_artifact(context, artifact_id, **kwargs):
        content = unaltered(context, artifact_id, **kwargs)
        return content.model_copy(update={"content": content.content + b"!"})

    routes.read_artifact = read_artifact

sys.exit(demo.main())
"""

#: The hours the demonstration must mean the same thing at.
#:
#: The service records a grant with its own clock, so whether the
#: demonstration works is a question about the hour -- and a test that only
#: ran it at the hour it happened to run at could not answer it. These two
#: are eighteen hours apart, and they straddle the instant at which a window
#: fixed to the demonstration's own moment closed for good: a
#: demonstration that still fixed its window there would pass at the first
#: and fail at the second. A window fixed there and *widened* would pass at
#: both, which is why the two runs are compared with each other and not
#: only with the exit code.
EARLY_HOUR: datetime = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)
LATE_HOUR: datetime = datetime(2026, 10, 21, 21, 0, tzinfo=UTC)

#: The program that runs the demonstration with its clock pinned.
#:
#: Every clock in the demonstration's process -- the demonstration's own and
#: the product's -- reads a pinned instant instead of the wall clock's, so
#: the hour the demonstration runs at is this test's to choose rather than
#: the machine's. **The pinned clock advances a second per read**, because
#: the clock a real service stamps a grant with moves on: the question and
#: the answer are never the same instant, and a window that does not cover
#: the distance between them is the defect this witness is for. It names the
#: instant it pinned at, and it refuses to run at all unless the clock the
#: service records a grant with really was pinned: a witness that ran the
#: demonstration at the wall clock's hour while claiming to have pinned it
#: would pass for the wrong reason.
PINNED_CLOCK_PROGRAM: str = """
import importlib.util
import sys
from datetime import datetime as _datetime, timedelta

import labcairn.application.approvals as approvals

pinned = _datetime.fromisoformat(sys.argv[2])
step = timedelta(seconds=1)
reads = [0]


class _AnyDatetime(type):
    def __instancecheck__(cls, instance):
        return isinstance(instance, _datetime)


class Pinned(_datetime, metaclass=_AnyDatetime):
    @classmethod
    def now(cls, tz=None):
        reads[0] += 1
        moment = pinned + step * reads[0]
        return moment.replace(tzinfo=tz) if tz is not None else moment.replace(tzinfo=None)


def pin(module):
    if getattr(module, "datetime", None) is _datetime:
        module.datetime = Pinned


spec = importlib.util.spec_from_file_location("g4_exit_demo", sys.argv[1])
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

for name, module in list(sys.modules.items()):
    if module is not None and name.startswith("labcairn"):
        pin(module)

pin(demo)

if getattr(approvals, "datetime", None) is not Pinned:
    raise SystemExit("the clock the service records a grant with is not pinned")
if getattr(demo, "datetime", None) is not Pinned:
    raise SystemExit("the demonstration's own clock is not pinned")

print(f"clock pinned at {pinned.isoformat()}, advancing a second per read")
raise SystemExit(demo.main())
"""


@pytest.fixture(scope="module")
def demonstration(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, once for the whole module.

    Its own temporary workspace and database, so it leaves nothing behind and
    needs nothing from the test.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set because the child's output
    encoding and terminal width are otherwise the machine's business, and
    neither is a fact about the demonstration.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return subprocess.run(
        [sys.executable, str(DEMO)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=900,
        cwd=repo_root,
    )


@pytest.fixture(scope="module")
def planted_claim_run(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, with one of its claims planted false.

    The fault is planted from outside the demonstration: its own ``check()``
    is wrapped, so the claim's *condition* is false while the demonstration's
    source is untouched. What the test then observes is the demonstration's
    exit code, which is the thing the run is for.
    """
    return _run_with_a_fault(repo_root, "planted-claim", PLANTED_CLAIM)


@pytest.fixture(scope="module")
def altered_bytes_run(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, with the service serving the wrong bytes.

    The defect is planted from outside the demonstration: the API route's own
    read of the artefact is wrapped, so the service answers with the stored
    bytes and one more. Nothing in the repository is edited, and the
    demonstration is run exactly as it is run everywhere else.
    """
    return _run_with_a_fault(repo_root, "altered-bytes")


@pytest.mark.e2e
def test_the_exit_demonstration_runs_and_every_check_holds(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration exits zero, and every claim it makes was made.

    A failure here is a failure of the demonstration, not of the
    demonstration's environment: it exits non-zero because a ``check()``
    raised, and the assertion prints the whole of its output so the failing
    claim is the first thing a reader sees.

    **The count of its checks is compared with the count it should make.** A
    claim the demonstration failed and then carried on from is counted
    neither in the lines it printed nor in its own summary, so a floor would
    not see it: the count is the number, and the number is the witness.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for step in STEPS:
        assert step in output, f"the demonstration never reached the step {step!r}"

    checks = [line for line in output.splitlines() if line.strip().startswith("[ok]")]
    assert checks, "the demonstration printed no checks at all"
    assert len(checks) == EXPECTED_CHECKS, (
        f"the demonstration made {len(checks)} check(s); it makes "
        f"{EXPECTED_CHECKS}, so a claim was removed -- or a claim failed and "
        "the demonstration carried on from it, which is counted by neither "
        "the lines nor the summary"
    )
    assert f"{len(checks)} checks passed." in output, (
        "the demonstration's own count of its checks does not match the number "
        "it printed, so its summary is not a fact about the run"
    )

    # The two claims about the approval the demonstration asked the service
    # for: the exit code says the demonstration held every claim it made,
    # but not that it made these two.
    for claim in (
        "the approval asked for outlives the wall clock's now",
        "the grant was recorded inside the approval's own window",
    ):
        assert claim in output, f"the demonstration never made the claim {claim!r}"


@pytest.mark.e2e
def test_the_demonstration_means_the_same_thing_at_any_hour(repo_root: Path) -> None:
    """The demonstration runs at an hour of this test's choosing, not only at this one.

    The service records a grant with its own clock, and the store refuses a
    grant of an approval that has lapsed -- so an approval the demonstration
    asked for with a moment of its own would lapse before the service
    stamped the grant, and the demonstration would work in the morning and
    fail in the evening. **A demonstration whose outcome depends on the hour
    is not a demonstration of the product**, and a test that only ran it at
    the hour it happened to run at would not see that at all.

    So the hour is this test's to choose: the demonstration is run twice,
    with every clock in it -- the demonstration's own and the product's --
    pinned to an instant, at two hours eighteen apart that straddle the
    instant at which a window fixed to the demonstration's own moment closed
    for good. A demonstration that still fixed its window there would pass
    at the first and fail at the second.

    **The pinned clock moves**, because the clock a real service stamps a
    grant with moves on: the question and the answer are never the same
    instant, and a window that does not cover the distance between them is
    the defect this witness is for. So the grant is recorded strictly after
    the moment the demonstration asked, and the approval the demonstration
    asked for has to outlive that.

    **The pin is checked, not assumed.** The program that pins the clocks
    refuses to run unless the clock the service records a grant with really
    was pinned, and says which instant it pinned at; a run that said
    nothing about the hour would be evidence about nothing.

    **And the expiry moved with the hour.** That is the claim that no
    single run can make: a window fixed to a moment of the demonstration's
    own would outlive the grant at every hour it was checked, and would be
    caught only by waiting for the hour it closed at. Two runs eighteen
    hours apart catch it at once, because a window that does not read the
    clock does not move when the clock does.
    """
    expiries: dict[datetime, datetime] = {}
    for moment in (EARLY_HOUR, LATE_HOUR):
        run = run_at(repo_root, moment)
        assert run.returncode == 0, (
            f"the demonstration failed with its clock pinned to {moment.isoformat()}:\n"
            f"{run.stdout}\n{run.stderr}"
        )
        assert f"clock pinned at {moment.isoformat()}" in run.stdout, (
            "the demonstration did not run with its clock pinned, so the run says "
            "nothing about the hour"
        )
        expiry = re.search(r"expiry\s+:\s+(\S+)", run.stdout)
        assert expiry is not None, (
            "the demonstration never said when the approval it asked for lapses"
        )
        expiries[moment] = datetime.fromisoformat(expiry.group(1))
        assert expiries[moment] > moment, (
            f"the approval the demonstration asked for lapses at {expiry.group(1)}, "
            f"which is not after the hour it was asked at ({moment.isoformat()})"
        )
        granted = re.search(r"granted (\S+), lapses (\S+)", run.stdout)
        assert granted is not None, "the demonstration never said when the grant was recorded"
        assert datetime.fromisoformat(granted.group(1)) > moment, (
            f"the grant was recorded at {granted.group(1)}, which is not after the "
            f"hour the demonstration was pinned to ({moment.isoformat()}); the clock "
            "did not move between the question and the answer"
        )

    moved = expiries[LATE_HOUR] - expiries[EARLY_HOUR]
    apart = LATE_HOUR - EARLY_HOUR
    assert abs(moved - apart) <= timedelta(minutes=1), (
        f"the approval the demonstration asked for lapses {moved} apart in the two "
        f"runs, but the two hours are {apart} apart: the expiry did not move with "
        "the clock"
    )


@pytest.mark.e2e
def test_a_claim_that_does_not_hold_makes_the_run_fail(
    planted_claim_run: subprocess.CompletedProcess[str],
) -> None:
    """A claim the demonstration cannot support makes the run fail.

    **The converse of what the clean run asserts.** The clean run says a zero
    exit means every claim held; this says a claim that does not hold means a
    non-zero exit, which is the half the clean run cannot see. A
    demonstration that printed its lines and swallowed every failure would
    still exit zero, and the clean run would still be green.

    The claim is planted from outside -- the demonstration's ``check()`` is
    wrapped, so the condition is false while the demonstration's own source
    is untouched -- and the failure has to name the claim that was planted,
    so that a run which died for some other reason does not pass here.
    """
    output = planted_claim_run.stdout
    error = planted_claim_run.stderr

    assert planted_claim_run.returncode != 0, (
        "the demonstration exited zero with a claim planted false, so its exit "
        "code says nothing about whether its claims hold: " + output
    )
    assert f"FAILED: {PLANTED_CLAIM}" in error, (
        f"the run failed, but not on the claim that was planted false: {error}"
    )
    assert "checks passed." not in output, (
        "the demonstration reported that every one of its checks held, so the "
        "planted claim did not stop the run"
    )
    assert "[ok] the command succeeded" in output, (
        "the demonstration never reached the claim that was planted false, so "
        "the run failed before the plant could do anything"
    )


@pytest.mark.e2e
def test_the_demonstration_fails_when_the_service_serves_the_wrong_bytes(
    altered_bytes_run: subprocess.CompletedProcess[str],
) -> None:
    """A real defect in the product makes the run fail.

    The claim this witnesses is the one the exit test is named for -- "CLI and
    Web produce the same versioned report" -- and it is witnessed by the
    demonstration's own comparison of the file the CLI names against the bytes
    the service serves. A demonstration that swallowed its failures would exit
    zero here, with a service that was serving bytes the file did not hold.
    """
    output = altered_bytes_run.stdout
    error = altered_bytes_run.stderr

    assert altered_bytes_run.returncode != 0, (
        "the demonstration exited zero with the service serving bytes that are "
        "not the stored file's bytes, so the report's bytes were never really "
        "compared: " + output
    )
    assert "FAILED: the report.md the CLI names is the bytes the API serves" in error, (
        "the run failed, but not on the report's bytes: " + error
    )
    assert "5. The three surfaces agree" in output, (
        "the demonstration never reached the comparison of the report's bytes"
    )


@pytest.mark.e2e
def test_the_two_surfaces_were_compared_against_one_store(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The CLI's task state and the API's task document were compared, field by field.

    The comparison is the gate's exit test, and what makes it evidence is the
    *number of fields*: a comparison of two empty documents would also say
    "no differences", so the count is what says the comparison happened over
    the task and not over nothing.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    compared = re.search(r"compared\s+:\s+(\d+) field\(s\), (\d+) differing", output)
    assert compared is not None, "the demonstration never reported a field-by-field comparison"
    assert int(compared.group(1)) > 100, (
        f"only {compared.group(1)} field(s) were compared; the task document has "
        "far more than that, so the comparison was over too little"
    )
    assert compared.group(2) == "0", (
        f"{compared.group(2)} field(s) differed between the CLI's task state and the "
        "API's task document"
    )


@pytest.mark.e2e
def test_the_report_bytes_were_compared_by_hash(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """Each of the four forms was compared as stored against as served.

    The hash is the comparison: the file the report operation wrote and the
    bytes the API serves are the same bytes, for each of the four forms. A
    comparison against a *re-render* would also be a hash comparison, and
    would prove something else -- so the demonstration names the stored file.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for form in ("report.md", "report.html", "report.docx", "report.pdf"):
        assert f"the {form} the CLI names is the bytes the API serves" in output, (
            f"the demonstration never compared the {form} as stored against as served"
        )


@pytest.mark.e2e
def test_the_material_was_ingested_through_the_cli(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration put the material in the ledger through the CLI.

    A demonstration that called the material module directly would still
    work, and would still print its "ok" lines; what it would not be is a
    demonstration of the surfaces agreeing. So the two lines that say the CLI
    did it are asserted here.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "the task holds the material the CLI was told about" in output, (
        "the demonstration did not bind the material through the CLI"
    )
    assert "the CLI can report the material it ingested" in output, (
        "the demonstration did not report the material through the CLI"
    )


@pytest.mark.e2e
def test_the_two_surfaces_were_driven_against_one_workspace(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The CLI and the service drove one workspace at the same time.

    A request owns its session and closes it when it is over, so the service
    holds the store's write lock for nobody between requests, and the CLI's
    writer is not refused for it. The demonstration's own line says the two
    were used together, and the check behind it says the CLI's command
    succeeded while the service was serving.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "the CLI and the service were used against one workspace at the same time" in output, (
        "the demonstration did not drive the CLI and the service against one workspace"
    )


@pytest.mark.e2e
def test_every_comparison_was_shown_a_difference_it_had_to_find(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """Each comparison in the demonstration can fail, and this is the evidence.

    A comparison that compares nothing also reports "no differences", so a
    demonstration whose comparisons had been narrowed would still print its
    "ok" lines and still pass the test above. The demonstration therefore runs
    each comparison once over something that must answer the other way, and
    insists it finds the difference.

    **This test reads the demonstration's output for that evidence**, because
    a control inside the demonstration that the test cannot see is the same
    defect one level down. The assertion is on the control's own "[ok]" line,
    so what is witnessed is a control that *passed*, not one that was merely
    named.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for control in (
        "the field-by-field comparison finds the difference it was given",
        "the byte comparison finds the difference it was given",
        "the re-read comparison finds the difference it was given",
        "the unchanged-bytes comparison finds the difference it was given",
        "the staleness requirement finds the difference it was given",
        "the resolution comparison finds the difference it was given",
        "the refusal comparison finds the difference it was given",
        "the refusal comparison tells this refusal from another",
        "the staleness comparison finds the difference it was given",
        "the staleness comparison says no about a receipt the walk did not mark",
        "the changed-hash comparison finds the difference it was given",
        "the staleness walk says nothing is stale while the material is unchanged",
    ):
        assert f"[ok] {control}" in output, (
            f"the demonstration never ran the control {control!r}, so its comparison "
            "cannot be told from one that compares nothing"
        )

    # And the evidence itself: the planted difference was found, and it was
    # one field.
    planted = re.search(r"control\s+:\s+(\d+) field\(s\) differ in the altered copy", output)
    assert planted is not None, "the demonstration never reported the control's finding"
    assert int(planted.group(1)) == 1, (
        f"the control found {planted.group(1)} difference(s) in the altered copy; "
        "exactly one was planted"
    )

    # The refusal requirement, over the two grant requests: the service
    # refused one of them, and it was the second. A demonstration that only
    # said "the second was refused" would not say how many were refused.
    refused = re.search(r"the service refused: \[(.+)\]", output)
    assert refused is not None, "the demonstration never reported which grant requests were refused"
    assert refused.group(1) == "'repeated'", (
        f"the demonstration reported that the service refused {refused.group(1)}; "
        "the repeated grant is the only one of the two that should be refused"
    )


@pytest.mark.e2e
def test_the_re_read_comparison_was_shown_a_difference_it_had_to_find(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The workbench's re-read was compared against something that must differ.

    The comparison the re-read makes is "the first read is the second read",
    and a comparison that compares nothing also reports "the same". The
    demonstration therefore runs that comparison once over a copy of the
    second read with a difference planted in it, and insists the comparison
    finds it.

    **The test reads the demonstration's output for that evidence**, because
    a control the test cannot see is the same defect one level down. A
    comparison narrowed to "the first read is the first read" would fail this
    control, and the run would not reach the end of the path.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout
    assert "[ok] the re-read comparison finds the difference it was given" in output, (
        "the demonstration never ran the re-read's control, so the comparison "
        "cannot be told from one that compares nothing"
    )


@pytest.mark.e2e
def test_the_revision_bytes_comparison_was_shown_a_difference_it_had_to_find(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The first revision's bytes were compared against bytes that must differ.

    The claim is that the re-render left the first revision alone, and it is
    witnessed by measuring the revision twice: a comparison that compares
    nothing also reports "the same". The demonstration therefore measures a
    copy of the revision with a file's bytes altered, and insists the
    comparison finds the difference.

    A comparison narrowed to "the first measurement is the first
    measurement" would fail this control, and the run would not reach the end
    of the path.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout
    assert "[ok] the unchanged-bytes comparison finds the difference it was given" in output, (
        "the demonstration never ran the revision-bytes control, so the "
        "comparison cannot be told from one that compares nothing"
    )


@pytest.mark.e2e
def test_the_staleness_requirement_was_shown_a_difference_it_had_to_find(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The requirement over the walk's receipts was asked about one that does not qualify.

    The claim is that every receipt the walk marked stale is stale by the
    repository's own reason, and a requirement that compares nothing also
    reports "every one of them". The demonstration therefore asks the same
    requirement about the walk's receipts with one of them given another
    reason, and insists the requirement says no.

    A requirement narrowed to a constant would fail this control, and the run
    would not reach the end of the path.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout
    assert "[ok] the staleness requirement finds the difference it was given" in output, (
        "the demonstration never ran the staleness requirement's control, so "
        "the requirement cannot be told from one that compares nothing"
    )


@pytest.mark.e2e
def test_the_report_was_marked_stale_when_the_material_moved(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The report's own receipt is among the artefacts the walk marked stale.

    The demonstration's own check is about the **material** rather than about
    the report, because what a report's chain names depends on what the
    report was built from -- a figure, a table, or a claim -- and the walk
    is one hop. So the demonstration prints the stale receipts and the
    report's receipt id, and **this test reads the two and compares them**:
    a demonstration that left the report out of the stale receipts, or that
    named a receipt the walk did not mark, fails here.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    stale = re.findall(r"^\s+stale\s+(\S+)$", output, flags=re.MULTILINE)
    assert stale, "the demonstration named no stale artefact"
    report = re.search(r"report receipt\s+:\s+(\S+)", output)
    assert report is not None, "the demonstration never named the report's receipt"
    assert report.group(1) in stale, (
        f"the report's receipt {report.group(1)} is not among the artefacts the "
        f"walk marked stale: {stale}"
    )


@pytest.mark.e2e
def test_the_report_carries_a_claim_cited_to_the_ingested_material(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The report carries a claim, and the claim rests on the ingested material.

    A claim rests on a cited record, and a citation points into material the
    task holds. The task holds the material because the CLI ingested it, so
    the report is not carrying disclosures only.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "the report carries the claim, and cites the address it rests on" in output, (
        "the demonstration's report carried no claim"
    )
    claims = re.search(r"claims\s+:\s+(\d+)", output)
    assert claims is not None, "the demonstration never reported how many claims it carried"
    assert int(claims.group(1)) >= 1, "the demonstration's report carried no claim"


@pytest.mark.e2e
def test_the_refusals_were_refusals_with_a_reason(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """A foreign origin, a missing token and a spent approval were each refused.

    Asserted on the reasons rather than on the messages, because a reason is
    a closed vocabulary: ``origin_refused`` and ``session_required`` are
    different facts, and a demonstration that printed the same word for both
    would pass a test that looked at the prose.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "origin_refused" in output, "a request from another origin was not refused"
    assert "session_required" in output, "a mutation without the token was not refused"
    assert "approval_refused" in output, "the same grant was applied twice"


@pytest.mark.e2e
def test_the_staleness_came_from_the_repositorys_own_walk(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The report was marked stale by the repository's walk, with its own reason.

    The reason is the repository's constant, imported here and compared: a
    demonstration that composed its own sentence would still say something was
    stale, and the reason for believing it is that the sentence is the
    repository's.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert STALE_REASON in output, (
        "the demonstration did not record the repository's own staleness reason"
    )
    assert (
        "the repository's own walk marked the artefacts whose chain names the material" in output
    ), "the demonstration did not use the repository's walk"


@pytest.mark.e2e
def test_the_demonstration_says_what_it_did_not_exercise(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The two known limits were named in the demonstration's own output.

    The event stream is not consumed by the workbench, and the workbench
    cannot switch the selected project. A demonstration that quietly passed
    over both would read as a demonstration of something it is not.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "What this did not exercise" in output, (
        "the demonstration did not say what it did not exercise"
    )
    assert "event stream" in output, "the event stream's absence was not named"
    assert "switch the selected project" in output, (
        "the inability to switch the selected project was not named"
    )
    assert "controls are not exhaustive" in output, (
        "the demonstration did not name the limit of its own controls"
    )


@pytest.mark.e2e
def test_the_demonstrations_workspace_is_outside_the_repository(
    demonstration: subprocess.CompletedProcess[str],
    repo_root: Path,
) -> None:
    """The workspace the demonstration made is not inside the checkout.

    A workspace inside the repository would make the run depend on the tree it
    runs in -- and would leave the checkout dirty, which is what "a clean
    clone" is about.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr

    made = re.search(r"workspace\s+:\s+(\S+)", demonstration.stdout)
    assert made is not None, "the demonstration never said which workspace it made"
    workspace = Path(made.group(1))
    assert not workspace.is_relative_to(repo_root), (
        f"the demonstration's workspace {workspace} is inside the repository {repo_root}"
    )


@pytest.mark.integration
def test_the_cli_and_the_api_agree_about_the_task(tmp_workspace: Path) -> None:
    """The two surfaces' task documents are the same, read by the test itself.

    The demonstration compares them too, but a comparison made inside the
    demonstration is a comparison the demonstration could get wrong -- narrowed
    to one field, or made against a document it derived in-process rather
    than one the service served. This one is made by the test, which asks each
    surface and compares what comes back, so a product in which the CLI and
    the API disagree fails here even so.

    **Field by field, and the difference is named.** A comparison that said
    only "they differ" would not say what differed, and a comparison that
    said "they agree" over two empty documents would agree about nothing.
    """
    assert run_cli(tmp_workspace, "init").returncode == 0
    created = run_cli(
        tmp_workspace,
        "task",
        "create",
        "--title",
        "Two surfaces, one task",
        "--objective",
        "See that both say the same thing.",
        "--criterion",
        "Field for field.",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    task_id = TaskId(json.loads(created.stdout)["task_id"])

    cli = run_cli(tmp_workspace, "task", "status", "--json")
    assert cli.returncode == 0, cli.stderr
    cli_state: dict[str, Any] = json.loads(cli.stdout)

    location = locate(tmp_workspace)
    config = read_config(location)
    with (
        application_context(location, config, task_id) as context,
        TestClient(create_app(context)) as client,
    ):
        api_state: dict[str, Any] = client.get("/task").json()

    cli_leaves = _leaves(cli_state)
    api_leaves = _leaves(api_state)
    differing = sorted(
        name
        for name in set(cli_leaves) | set(api_leaves)
        if cli_leaves.get(name) != api_leaves.get(name)
    )
    assert len(cli_leaves) >= 8, (
        f"only {len(cli_leaves)} field(s) were compared; a task document carries "
        "more than that, so the comparison was over too little"
    )
    assert str(task_id) in cli_leaves.values(), (
        "the comparison did not cover the task's own identity, so it was not a "
        "comparison of two documents about this task"
    )
    assert not differing, (
        f"{len(differing)} field(s) differ between the CLI's task state and the "
        f"API's task document: {differing}"
    )


def _leaves(document: Any, path: str = "") -> dict[str, Any]:
    """Every leaf of a document, by the path that names it."""
    if isinstance(document, Mapping):
        found: dict[str, Any] = {}
        for key, value in document.items():
            found.update(_leaves(value, f"{path}.{key}"))
        return found
    if isinstance(document, list):
        found = {}
        for index, value in enumerate(document):
            found.update(_leaves(value, f"{path}[{index}]"))
        return found
    return {path: document}


def _run_with_a_fault(
    repo_root: Path, mode: str, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """The demonstration, run as a person runs it, with a fault planted in it.

    The child is the demonstration itself -- the same file, the same command
    line -- and the fault is planted by the driver before the demonstration
    runs. So what the test observes is the demonstration's own behaviour under
    the fault, and the thing it observes is the exit code.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set for the same reason the
    clean run sets them: the child's output encoding and terminal width are
    the machine's business, and neither is a fact about the demonstration.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return subprocess.run(
        [sys.executable, "-c", DRIVER, str(DEMO), mode, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=900,
        cwd=repo_root,
    )
