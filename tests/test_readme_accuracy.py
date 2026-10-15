"""README accuracy gate — LC-P1-01 acceptance: *quick-start does not claim
unimplemented commands*.

Why this file exists
--------------------
The README opens with "Features listed below are planned, not yet shipped". That
honesty is the project's core, and honesty held only by an author's good
intentions is not a property, it is a habit. This file turns it into a gate.

Four independent claims are checked:

1. **Command authenticity.** Every command in a fenced block of the README is
   extracted and matched against :data:`VERIFIED_COMMANDS`. Each of those is then
   *actually executed* in a subprocess — ``uv run pytest`` really collects the
   suite, ``uv run ruff check .`` really lints, ``pnpm test`` really runs Vitest.
   The table is fail-closed in both directions: a command the README does not
   document fails ("you added a command nobody ran"), and a documented command
   that is not in the table fails ("this is not verified"). Adding a command to
   the README therefore requires adding a row *and* making that row pass.
2. **No claims of unimplemented capability.** The repository has no CLI, no
   server, no database and no product feature (LC-P1-14 is where release shape is
   settled). Sentence-level scanning rejects "supports / provides / 支持 / 实现"
   claims that carry no planning qualifier. The existing "planned" and "not yet
   shipped" language is deliberately exempt — those annotations are correct.
3. **Licensing consistency.** LC-P1-01 is binding that no ``LICENSE`` file exists
   while copyright ownership is uncleared, and that the README must state the
   true status. If somebody later drops a real ``LICENSE`` into the root, this
   fails loudly instead of letting the README quietly become a lie.
4. **Status honesty.** The status banner must be at the top of the file, must
   name the planning posture, and must carry a non-empty disclaimer.

A note on one thing this file deliberately does **not** assert
-------------------------------------------------------------
``LICENSE.PENDING.md`` §2 forbids *third parties* from calling LabCairn
"open source", and the README does describe itself as "an open-source, local-first
AI research workspace" — while holding no license at all, which in OSI terms is
the opposite of open source. That tension is real and is reported to the project
lead rather than asserted away here: deciding how a license-less project should
describe itself is a positioning call, not a fact a test should silently settle.
Forcing it with a regex would have turned a judgement into a wall.

Determinism rule (docs/plans/LC-P1-01-task-breakdown.md §5.2): no wall clock, no
RNG. The subprocess calls below are the only I/O this module performs and they
are bounded by explicit timeouts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# How commands are found in the README
# ---------------------------------------------------------------------------

#: Fenced code blocks. Only ``` and ```bash are treated as executable; ```python
#: and ```text hold prose or illustrative snippets, never runnable instructions.
_FENCE_RE = re.compile(r"^```(?:bash|sh|shell)?[ \t]*$(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)

#: A line that is an instruction rather than prose, a comment or a blank.
_SHELL_COMMENT_RE = re.compile(r"^\s*#")


def readme_text(repo_root: Path) -> str:
    """Raw README contents, decoded as UTF-8."""
    return (repo_root / "README.md").read_text(encoding="utf-8")


def documented_commands(text: str) -> list[str]:
    """Every runnable command line the README shows, in document order.

    Returns normalised (whitespace-collapsed) strings so that line wrapping in the
    Markdown cannot make a real command look like a new one.
    """
    commands: list[str] = []
    for block in _FENCE_RE.findall(text):
        for raw_line in block.splitlines():
            line = " ".join(raw_line.strip().split())
            if not line or _SHELL_COMMENT_RE.match(raw_line):
                continue
            commands.append(line)
    return commands


# ---------------------------------------------------------------------------
# The verified set — each row is executed for real by :func:`test_readme_commands_run`
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifiedCommand:
    """One README command, and the subprocess that proves it still works.

    ``documented`` is the exact text that must appear in a README code block.
    ``argv`` is what actually gets run; it differs from ``documented`` only where
    the difference is forced and is then stated in ``note``.
    ``unchanged`` lists repository files that must be byte-identical before and
    after the run, so an install command that silently rewrites a lockfile fails.
    """

    name: str
    documented: str
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_s: float = 300.0
    note: str = ""
    unchanged: tuple[str, ...] = field(default=())


VERIFIED_COMMANDS: tuple[VerifiedCommand, ...] = (
    VerifiedCommand(
        name="uv sync",
        documented="uv sync",
        argv=("uv", "sync"),
        unchanged=("uv.lock",),
        note="Runs the real install. uv.lock must survive it byte-identical; if pyproject "
        "drifted, uv would re-lock and this row fails instead of accepting the churn.",
    ),
    VerifiedCommand(
        name="uv run pytest",
        documented="uv run pytest",
        argv=("uv", "run", "pytest", "--collect-only", "-q", "tests"),
        note="`--collect-only` is forced: running the full suite from inside the suite "
        "would recurse. It still proves the venv resolves, pytest starts and every test "
        "module imports — which is the part of `uv run pytest` that can break.",
    ),
    VerifiedCommand(
        name="uv run ruff check",
        documented="uv run ruff check .",
        argv=("uv", "run", "ruff", "check", "."),
    ),
    VerifiedCommand(
        name="uv run ruff format --check",
        documented="uv run ruff format --check .",
        argv=("uv", "run", "ruff", "format", "--check", "."),
    ),
    VerifiedCommand(
        name="uv run mypy",
        documented="uv run mypy",
        argv=("uv", "run", "mypy"),
    ),
    VerifiedCommand(
        name="pnpm install",
        documented="pnpm install --frozen-lockfile",
        argv=("pnpm", "install", "--frozen-lockfile"),
        cwd="web",
        timeout_s=600.0,
        unchanged=("pnpm-lock.yaml",),
        note="--frozen-lockfile is the CI form: it fails rather than resolving a new one.",
    ),
    VerifiedCommand(
        name="pnpm test",
        documented="pnpm test",
        argv=("pnpm", "test"),
        cwd="web",
        note="Runs the real Vitest suite via the package.json `test` script.",
    ),
    VerifiedCommand(
        name="pnpm typecheck",
        documented="pnpm typecheck",
        argv=("pnpm", "typecheck"),
        cwd="web",
    ),
    VerifiedCommand(
        name="pnpm lint",
        documented="pnpm lint",
        argv=("pnpm", "lint"),
        cwd="web",
    ),
    VerifiedCommand(
        name="pnpm format:check",
        documented="pnpm format:check",
        argv=("pnpm", "format:check"),
        cwd="web",
    ),
)

#: Commands whose execution needs the Node toolchain and an installed web tree.
_WEB_COMMANDS = frozenset(c.name for c in VERIFIED_COMMANDS if c.cwd == "web")


def _run(argv: tuple[str, ...], cwd: Path, timeout_s: float) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` with the same name resolution an interactive shell would use.

    On Windows a user typing ``pnpm test`` gets ``pnpm.CMD`` because the shell
    consults ``PATHEXT``. ``CreateProcess`` does not, so passing the bare name
    raises FileNotFoundError for the exact command the README documents. Resolving
    with ``shutil.which`` and routing ``.cmd``/``.bat`` through ``cmd /c``
    reproduces the shell's behaviour instead of weakening the command being tested.
    """
    resolved = shutil.which(argv[0])
    if resolved is None:
        msg = f"executable {argv[0]!r} is not on PATH; cannot verify it"
        raise FileNotFoundError(msg)
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        command: list[str] = [os.environ.get("COMSPEC", "cmd.exe"), "/c", resolved, *argv[1:]]
    else:
        command = [resolved, *argv[1:]]
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        shell=False,
    )


def _skip_reason(command: VerifiedCommand, repo_root: Path) -> str | None:
    """Why this command cannot be executed here, or ``None`` if it can be."""
    if command.cwd == "web" or command.name in _WEB_COMMANDS:
        if shutil.which("pnpm") is None or shutil.which("node") is None:
            return "pnpm/node not on PATH (the Python suite still enforces the README)"
        if not (repo_root / "web" / "node_modules").is_dir():
            return "web/node_modules absent; run `pnpm install --frozen-lockfile` in web/ first"
    return None


# ---------------------------------------------------------------------------
# 1. Command authenticity
# ---------------------------------------------------------------------------


def test_readme_has_at_least_one_documented_command(repo_root: Path) -> None:
    """Guards the extractor itself.

    Without this, an empty or broken fenced-block regex would make
    :func:`test_readme_documents_only_verified_commands` pass on zero commands —
    the classic "the test is green because it found nothing" failure.
    """
    commands = documented_commands(readme_text(repo_root))
    assert commands, (
        "found no runnable command in README.md. Either the quick-start block was "
        "removed (the LC-P1-01 gate then has nothing to check) or its fence markers "
        "stopped matching ```bash blocks"
    )


def test_readme_documents_only_verified_commands(repo_root: Path) -> None:
    """Fail-closed: a command appears in the README only if it has a verified row.

    This is the assertion that makes "quick-start does not claim unimplemented
    commands" bite at edit time, before anyone runs anything.
    """
    known = {c.documented for c in VERIFIED_COMMANDS}
    unknown = [cmd for cmd in documented_commands(readme_text(repo_root)) if cmd not in known]
    assert not unknown, (
        "README documents command(s) with no verified row in "
        "tests/test_readme_accuracy.py::VERIFIED_COMMANDS: "
        f"{unknown}. Add a VerifiedCommand row for each and make it execute, or remove "
        "it from the README. Do not add a row for a command that does not work."
    )


def test_verified_commands_are_all_documented(repo_root: Path) -> None:
    """The other direction: no dead rows, so the table cannot rot into fiction."""
    commands = documented_commands(readme_text(repo_root))
    missing = [c.documented for c in VERIFIED_COMMANDS if c.documented not in commands]
    assert not missing, (
        f"VERIFIED_COMMANDS rows exist that the README no longer documents: {missing}. "
        "Either the README lost the command or the row should be deleted."
    )


def test_documented_uv_targets_exist(repo_root: Path) -> None:
    """Structural half of the uv check: the files `uv` acts on are really there.

    `uv sync` resolves ``pyproject.toml``/``uv.lock``; `uv run pytest` collects
    ``tests/``; `uv run mypy`` is scoped by ``[tool.mypy] files``. Each of those
    paths existing is a precondition for the command meaning anything.
    """
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    for relative in ("pyproject.toml", "uv.lock", ".python-version", "src/labcairn", "tests"):
        assert (repo_root / relative).exists(), f"`uv` commands depend on {relative}, which is gone"

    mypy_files: list[str] = pyproject["tool"]["mypy"]["files"]
    for entry in mypy_files:
        assert (repo_root / entry).exists(), (
            f"[tool.mypy] files lists {entry!r}, which does not exist; `uv run mypy` would "
            "fail or silently check nothing"
        )

    lock_python = (repo_root / ".python-version").read_text(encoding="utf-8").strip()
    requires = pyproject["project"]["requires-python"]
    assert lock_python in requires, (
        f".python-version pins {lock_python!r} but requires-python is {requires!r}; "
        "`uv sync` would provision an interpreter the project does not support"
    )


def test_documented_pnpm_scripts_exist_in_package_json(repo_root: Path) -> None:
    """Structural half of the pnpm check, and it always runs — no Node needed.

    This is deliberately separate from the execution test so that on a CI runner
    without an installed web tree the README is *still* checked against
    ``web/package.json``. A script that was renamed or deleted fails here even
    when `pnpm test` could not be run at all.
    """
    manifest = json.loads((repo_root / "web" / "package.json").read_text(encoding="utf-8"))
    scripts: dict[str, str] = manifest["scripts"]
    documented = [c.documented for c in VERIFIED_COMMANDS if c.documented.startswith("pnpm ")]

    assert documented, "no pnpm commands are documented; the web baseline check would be vacuous"

    for command in documented:
        parts = command.split()
        if parts[1] == "install":
            # Flags belong to pnpm itself, not to a package script.
            assert (repo_root / "web" / "pnpm-lock.yaml").is_file(), (
                "`pnpm install --frozen-lockfile` needs web/pnpm-lock.yaml, which is absent"
            )
            continue
        name = parts[1]
        assert name in scripts, (
            f"README documents `{command}` but web/package.json defines no {name!r} script "
            f"(available: {sorted(scripts)})"
        )


def test_readme_commands_run(repo_root: Path) -> None:
    """Execute every verified command for real.

    This is the assertion the whole file exists for: not "the string is in the
    README" but "the string still works". Each subprocess must exit 0, and any
    lockfile named in ``unchanged`` must be byte-identical afterwards.

    Commands whose toolchain is absent are skipped *loudly* — their structural
    checks above still run — so a green run here can never mean "nothing was
    attempted" without saying so.
    """
    executed = 0
    skipped = 0
    for command in VERIFIED_COMMANDS:
        reason = _skip_reason(command, repo_root)
        if reason is not None:
            skipped += 1
            print(f"SKIP {command.documented!r}: {reason}")  # noqa: T201 - report, not product code
            continue

        workdir = (repo_root / command.cwd).resolve()
        before = {name: (workdir / name).read_bytes() for name in command.unchanged}

        result = _run(command.argv, workdir, command.timeout_s)
        executed += 1

        for name, payload in before.items():
            after = (workdir / name).read_bytes()
            assert after == payload, (
                f"`{' '.join(command.argv)}` rewrote {command.cwd}/{name}. A lockfile changing "
                "underneath a documented install command means the lock is no longer the "
                "reproducible record it is supposed to be."
            )

        assert result.returncode == 0, (
            f"README documents `{command.documented}` but running it failed "
            f"(exit {result.returncode}).\n"
            f"argv: {command.argv}\ncwd: {workdir}\n"
            f"--- stdout ---\n{result.stdout[-4000:]}\n"
            f"--- stderr ---\n{result.stderr[-4000:]}\n"
            f"(note: {command.note})"
        )

    # Stated unconditionally so a green run can never be mistaken for a run where
    # nothing was attempted. `pytest -s` shows the number; CI logs keep it.
    print(  # noqa: T201 - report, not product code
        f"README commands verified: {executed} executed, {skipped} skipped, "
        f"{len(VERIFIED_COMMANDS)} in the table"
    )
    assert executed + skipped == len(VERIFIED_COMMANDS)


def test_uv_is_on_path_when_running_under_uv(repo_root: Path) -> None:
    """The Python rows assume `uv` is runnable. Assert the assumption, do not infer it."""
    if shutil.which("uv") is None:
        print("uv not on PATH; the python-side command rows above were skipped")  # noqa: T201
        return
    result = _run(("uv", "--version"), repo_root, 60.0)
    assert result.returncode == 0, f"`uv --version` failed: {result.stderr[-2000:]}"


# ---------------------------------------------------------------------------
# 2. No claims of unimplemented capability
# ---------------------------------------------------------------------------

#: Words that assert a capability the code does not have. English forms are
#: word-bounded; CJK forms are matched literally because \b does not apply.
_TRIGGER_RE = re.compile(
    r"(?:支持|提供|具备|内置|已实现|一键)"
    r"|(?<![A-Za-z])(?:supports?|provides?|offers?|offering|implements?|ships\s+with|delivers?"
    r"|enables?|allows?\s+you\s+to|one[-\s]click)(?![A-Za-z])",
    re.IGNORECASE,
)

#: Qualifiers that make an aspirational sentence honest. Anything here in the
#: *same sentence* exempts the sentence. Kept narrow on purpose: a broad list
#: would launder over-claims instead of catching them.
_QUALIFIER_RE = re.compile(
    r"planned|planning|not yet|will (?:be|add|ship)|future|roadmap|candidate|intended"
    r"|aims? to|is being built|designed to|target|"
    r"规划|计划|尚未|将(?:会|要)?|预期|候选|目标|拟|旨在",
    re.IGNORECASE,
)

#: Status words that are false today regardless of surrounding context.
_OVERCLAIM_RE = re.compile(
    r"production[-\s]ready|fully implemented|now shipping|ready for production|generally available"
    r"|已上线|正式发布|现已支持|全面支持",
    re.IGNORECASE,
)

#: A capability trigger only counts as a claim about *this project* when the
#: sentence also names a product subject. Without this gate the detector fires on
#: ordinary research prose — "Which dataset supports a claim?" is a rhetorical
#: question, not a product promise, and a gate that cries wolf gets ignored.
_SUBJECT_RE = re.compile(
    r"labcairn|研迹|this project|the project|the cli|cli\b|the app|the application|the tool"
    r"|本项目|该项目|本工具|系统",
    re.IGNORECASE,
)

_LINK_OR_CODE_RE = re.compile(r"`[^`]*`|\[[^\]]*\]\([^)]*\)")
# Full-width terminators are escaped rather than typed literally: ruff's RUF001
# flags them as ambiguous Unicode, which is correct in general and noise here.
_SENTENCE_SPLIT_RE = re.compile("(?<=[.!?\\u3002\\uff01\\uff1f])\\s+")


def _prose_only(text: str) -> str:
    """Strip code fences, inline code and link targets before scanning claims.

    A command or a file path is not a claim; a link target certainly is not.
    """
    stripped = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    return _LINK_OR_CODE_RE.sub(" ", stripped)


def find_unsupported_claims(text: str) -> list[tuple[str, str, str]]:
    """Return ``(kind, sentence, reason)`` for every unqualified capability claim.

    A sentence is a line (so Markdown bullets stay intact) further split on
    sentence terminators. Two gates must both open before a trigger word becomes
    a finding: the sentence must name a product subject, and it must carry no
    planning qualifier. Released-status markers (:data:`_OVERCLAIM_RE`) need
    neither — "production-ready" is false about this project in any sentence.
    """
    findings: list[tuple[str, str, str]] = []
    for line in _prose_only(text).splitlines():
        for sentence in (s.strip() for s in _SENTENCE_SPLIT_RE.split(line)):
            if not sentence:
                continue
            if _OVERCLAIM_RE.search(sentence):
                findings.append(("overclaim-marker", sentence, "asserts a released/shipped status"))
            if (
                _TRIGGER_RE.search(sentence)
                and _SUBJECT_RE.search(sentence)
                and not _QUALIFIER_RE.search(sentence)
            ):
                findings.append(
                    (
                        "capability-claim",
                        sentence,
                        "claims a capability that does not exist yet, with no planning "
                        "qualifier in the same sentence",
                    )
                )
    return findings


def test_claim_detector_has_teeth() -> None:
    """Unit-test the detector on synthetic text, so a weakened regex fails here.

    Without this, an over-broad :data:`_QUALIFIER_RE` — say one that also matched
    the word "can" — would silently switch the README-level check off, and the
    only symptom would be a test suite that stays green forever.
    """
    must_flag = [
        "LabCairn 支持一键论文写作。",
        "LabCairn supports one-click paper writing.",
        "The CLI provides a web dashboard.",
        "LabCairn 已实现 PDF 解析。",
        "This release is production-ready.",
        "项目现已支持自动实验设计。",
    ]
    for sentence in must_flag:
        assert find_unsupported_claims(sentence), f"detector missed a real over-claim: {sentence!r}"

    must_not_flag = [
        # The existing README's own honest language must survive.
        "Features listed below are planned, not yet shipped.",
        "LabCairn is an open-source, local-first AI research workspace designed to help "
        "researchers work across papers, data, analysis and reports.",
        "It aims to make AI-assisted research inspectable.",
        "LabCairn is being built to make those questions first-class parts of the workflow.",
        "the remaining scientific libraries are **candidates** serving those same responsibilities",
        # Verbatim README text, suppressed from ruff's RUF001 (ambiguous-Unicode):
        # a full-width semicolon is correct Chinese punctuation, and testing the
        # detector against real CJK prose is the point of this row.
        "项目目前处于第一阶段建设中；尚未发布的能力均为规划目标。",  # noqa: RUF001
        "Planned first release (Phase 1)",
    ]
    for sentence in must_not_flag:
        findings = find_unsupported_claims(sentence)
        assert not findings, f"detector false-positived on honest text {sentence!r}: {findings}"


def test_readme_makes_no_unqualified_capability_claim(repo_root: Path) -> None:
    """The README itself, checked with the detector exercised above."""
    findings = find_unsupported_claims(readme_text(repo_root))
    assert not findings, (
        "README.md asserts capabilities that do not exist in this repository. LC-P1-14 is "
        "where release shape is settled; until then every such sentence needs a planning "
        "qualifier in the same sentence, or must be deleted.\n"
        + "\n".join(f"  [{kind}] {sentence!r} -- {reason}" for kind, sentence, reason in findings)
    )


def test_readme_does_not_document_a_product_cli(repo_root: Path) -> None:
    """No ``labcairn ...`` invocation may appear: no console script is declared.

    This is a structural claim, not a keyword list. ``pyproject.toml`` has no
    ``[project.scripts]`` table and ``src/labcairn/cli.py`` does not exist, so any
    ``labcairn <verb>`` line in the README is by construction an unimplemented
    command — exactly what the LC-P1-01 gate forbids. Typer merely being present
    as a transitive import is irrelevant and is deliberately not consulted.
    """
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert "scripts" not in pyproject["project"], (
        "pyproject.toml now declares [project.scripts]. If that entry point is real, the "
        "README may document it — add a VerifiedCommand row for it first, and revisit the "
        "no-CLI claim in tests/test_readme_accuracy.py."
    )
    assert not (repo_root / "src" / "labcairn" / "cli.py").exists(), (
        "src/labcairn/cli.py exists; the README's no-CLI claim and this gate both need "
        "reviewing before the CLI is documented"
    )

    # Case-sensitive and preceded-by-nothing: the console script would be spelled
    # lowercase `labcairn`, so the proper noun "LabCairn is ...", the repo slug
    # `gg320324492-lgtm/labcairn` and the sibling path `labcairn-upstreams/` are all
    # correctly not matches. Only a real invocation survives.
    offenders = [
        line.strip()
        for line in readme_text(repo_root).splitlines()
        if re.search(r"(?<![A-Za-z0-9_./-])labcairn\s+[a-z][a-z0-9-]*", line)
    ]
    assert not offenders, (
        "README documents a `labcairn ...` command but the project declares no console "
        f"script: {offenders}"
    )


def test_readme_names_only_paths_that_exist(repo_root: Path) -> None:
    """Every repository path the README points at is really there.

    A broken pointer to a document is a small lie about the project's state, and
    it is the cheapest kind to catch.
    """
    text = readme_text(repo_root)
    referenced: set[str] = set()
    referenced.update(re.findall(r"\[[^\]]*\]\(([^)]+)\)", text))
    referenced.update(
        m.group(1) for m in re.finditer(r"`((?:docs|src|tests|web|scripts)/[^`]+)`", text)
    )

    assert referenced, "no repository paths referenced; the link check would be vacuous"

    broken: list[str] = []
    for target in sorted(referenced):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        candidate = repo_root / target.split("#", 1)[0]
        if not candidate.exists():
            broken.append(target)

    assert not broken, (
        f"README.md references repository path(s) that do not exist: {broken}. "
        "LC-P1-01 requires the README to describe the repository as it is."
    )


# ---------------------------------------------------------------------------
# 3. Licensing status consistency
# ---------------------------------------------------------------------------


def test_repository_really_has_no_license_file(repo_root: Path) -> None:
    """The load-bearing fact behind every licensing statement in the README.

    If this fails, somebody has added a real license and the README — which says
    no rights have been granted — has become false. LICENSE.PENDING.md §5 requires
    ``LICENSE`` and ``LICENSE.PENDING.md`` to land in the same commit and never
    coexist, so this is the moment to reconcile the two, not to relax the test.
    """
    root = repo_root
    licence_files = sorted(
        p.name for p in root.iterdir() if p.is_file() and p.name.startswith("LICENSE")
    )
    unexpected = [name for name in licence_files if name != "LICENSE.PENDING.md"]

    assert not unexpected, (
        f"repository root now contains {unexpected}. LICENSE.PENDING.md §3 explains why a "
        "file named LICENSE carries a meaning a placeholder cannot: GitHub renders it as "
        "the project licence and forks inherit a claim never made. Either ownership was "
        "cleared (in which case update LICENSE.PENDING.md, the README and LC-P1-14 "
        "together) or remove the file. Do not simply update this assertion."
    )

    assert (root / "LICENSE.PENDING.md").is_file(), (
        "LICENSE.PENDING.md is missing. Without it the repository silently states nothing "
        "about its licensing, which is the failure mode §2 of that file exists to prevent."
    )


def test_readme_license_section_matches_license_pending(repo_root: Path) -> None:
    """README's licence wording must agree with LICENSE.PENDING.md, point by point.

    Each required phrase is checked as a substring of the lowercased README rather
    than by regex, so the assertion is about the sentence a human would read, not
    about a pattern that could be loosened. ``*`` emphasis markers are stripped
    first — otherwise bolding a word splits the phrase and the gate would report a
    licensing problem where the sentence is in fact correct.
    """
    text = readme_text(repo_root).lower().replace("*", "")
    required = {
        "states that no licence has been granted": "license status: not yet granted",
        "states that no LICENSE file exists": "no `license` file",
        "names the placeholder and denies it grants rights": "does not grant rights",
        "forbids reading the placeholder as MIT": "not be read as an mit grant",
        "marks MIT as planned rather than granted": "planned licensing remains mit",
        "names the unresolved PyMuPDF decision": "pymupdf",
    }
    missing = [description for description, phrase in required.items() if phrase not in text]
    assert not missing, (
        f"README.md licence statement does not match LICENSE.PENDING.md; missing: {missing}. "
        "LC-P1-01 requires the README to state the true licensing status — not granted, no "
        "LICENSE file, MIT is a plan, PyMuPDF unresolved."
    )


def test_readme_contains_no_unqualified_license_grant(repo_root: Path) -> None:
    """Assert no sentence claims a grant.

    ``Planned licensing remains MIT`` is honest and passes; ``MIT licensed``
    without a qualifier fails.
    """
    grant_phrases = (
        "mit licensed",
        "licensed under the mit",
        "licensed under mit",
        "mit licence",
        "permissively licensed",
        "we grant",
        "you may use, copy, modify",
    )
    hits: list[str] = []
    prose = _prose_only(readme_text(repo_root))
    for sentence in (s.strip() for s in _SENTENCE_SPLIT_RE.split(prose)):
        low = sentence.lower()
        if any(phrase in low for phrase in grant_phrases) and not _QUALIFIER_RE.search(sentence):
            hits.append(sentence)
    assert not hits, (
        "README.md contains an unqualified licence grant: "
        f"{hits}. LICENSE.PENDING.md §2: nothing in this repository is licensed to you, and "
        "silence is not permission."
    )


# ---------------------------------------------------------------------------
# 4. Status honesty
# ---------------------------------------------------------------------------


def test_status_banner_is_at_the_top_and_is_not_empty(repo_root: Path) -> None:
    """The status declaration must be near the top and must carry substance.

    A banner that merely exists is worth nothing; it has to name the planning
    posture and warn the reader off, which is what makes the rest of the README
    safe to publish while unimplemented.
    """
    lines = readme_text(repo_root).splitlines()
    head = "\n".join(lines[:8])

    banner = next(
        (line for line in lines[:8] if line.lstrip("> ").startswith("**Status:")),
        None,
    )
    assert banner is not None, (
        "no `> **Status: ...` declaration within the first 8 lines of README.md. A reader "
        "must learn the project is unbuilt before they read any capability claim.\n"
        f"--- first 8 lines ---\n{head}"
    )

    low = banner.lower()
    assert "planned" in low and "not yet shipped" in low, (
        f"the status banner no longer says the features are `planned, not yet shipped`: {banner!r}"
    )
    assert len(banner.strip()) > 120, (
        f"the status banner is too short to be a real statement: {banner!r}"
    )
    assert re.search(r"do not use", low) or re.search(r"not for", low), (
        "the status banner must warn the reader what the code must not be used for"
    )


def test_status_banner_names_the_current_phase(repo_root: Path) -> None:
    """A status that cannot go stale tells you nothing. Pin it to Phase 1."""
    banner = next(
        (line for line in readme_text(repo_root).splitlines()[:8] if "**Status:" in line),
        "",
    )
    assert "phase 1" in banner.lower(), (
        f"the status banner does not name the current phase, so it cannot be updated when the "
        f"phase moves: {banner!r}"
    )


def test_no_status_claim_contradicts_the_banner(repo_root: Path) -> None:
    """Nothing further down may re-open the question the banner closed."""
    text = readme_text(repo_root)
    contradictions = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith(">")
        and not _QUALIFIER_RE.search(line)
        and _OVERCLAIM_RE.search(line)
    ]
    assert not contradictions, (
        "README contains a released/shipped claim outside the status banner that contradicts "
        f"it: {contradictions}"
    )
