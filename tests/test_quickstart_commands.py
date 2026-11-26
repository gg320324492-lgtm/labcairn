"""The quickstart's commands and the README's are the same set.

Why this file exists
--------------------
``docs/RELEASE-NOTES.md`` §3 (finding 2) recorded a gap in the repository's
own witnessing: **the quickstart's command list was watched by nobody.** The
README's command list *is* watched — ``scripts/outsider_path.py`` compares it
with that script's own table in both directions, and
``tests/test_readme_accuracy.py`` executes every command the README shows.
The quickstart named commands that neither of those gates could see, so a
command could be renamed in one document and not the other, and the tree
stayed green while a reader followed a page that no longer worked.

This file closes that hole by putting the two documents side by side: the
commands the quickstart shows and the commands the README shows must be the
same set, and both directions fail.

How a command is read
---------------------
**The walk script's reader, and the CLI's own command tree.** A line of a
document shows a command when it is

* a line of a fenced block whose language is one of the walk script's shell
  languages (a line a person types), or
* an inline code span.

The **path** of a product command is resolved against the CLI's own command
tree, read from the application: ``labcairn task status``, ``labcairn init``,
``labcairn sources addresses``. The CLI is the authority on which commands
exist, so a document cannot name a command the CLI does not have and have it
read as a different command.

**The two documents spell the same command differently, and that is
allowed.** The README's table writes ``labcairn task status``; the quickstart
writes ``uv run labcairn --workspace ./workspace task status --json`` in its
by-hand path and the bare ``task status`` in prose. All three are the command
``task status``. The gate compares the *command*, never the line, and never
the prose around it.

What is compared
----------------
Two surfaces, each in both directions:

1. **The product surface** — the CLI command paths each document names.
   Fail-closed both ways: a command the quickstart names and the README does
   not is a failure, and so is the reverse.
2. **The maintained surface** — the repository's own commands (``uv sync``,
   ``uv run pytest``, the ``pnpm`` scripts, ...). The walk script's table
   (``README_COMMANDS``) is the authority for this set, because that is the
   table the README is already checked against; the two documents are checked
   against the same authority and against each other.

   The quickstart's by-hand path also shows steps the README does not:
   making the research folder, copying the material into it, and running the
   walk script. Those are **steps of the walk**, not maintained commands, and
   are recognised by what they name — the walk's own material folder or the
   walk script — not by a list kept here.

What would make this file red
-----------------------------
* A command renamed on one page and not the other (both directions).
* A command the README documents and the quickstart does not show, or the
  reverse — including a maintained command dropped from the quickstart's §7
  witness table.
* A document naming a command the CLI does not have.
* A maintained command that is neither in the walk script's table nor a step
  of the walk.
* The extractor silently finding nothing (the guards below).

Determinism rule: this file reads two tracked documents, the walk script and
the package's own command tree. It runs no subprocess and reads no clock.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import typer.main

from labcairn.cli.commands import app as _cli_app


def _load_the_walk_script() -> Any:
    """The walk script, loaded as a module.

    **The script is a tool rather than a package**, so it is loaded the way a
    person would run it: by its own path. It is loaded under a name of its
    own so the two gates' loads do not collide.
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "outsider_path.py"
    spec = importlib.util.spec_from_file_location("quickstart_gate_walk_script", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The module is registered before it runs: a dataclass asks
    # ``sys.modules`` for its own namespace while it is being built.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


#: The walk script -- the reader every other gate that reads a document's
#: commands uses. **Its parts, not a second extractor**: the walk script
#: pairs its fences fence by fence, and a second pairing here would be a
#: second answer.
WALK_SCRIPT: Any = _load_the_walk_script()

#: The languages a fenced block may hold a command in.
SHELL_LANGUAGES: frozenset[str] = frozenset(WALK_SCRIPT.SHELL_LANGUAGES)

#: The CLI's own command tree, read from the application -- the authority on
#: which commands exist.
_CLI_ROOT: Any = typer.main.get_command(_cli_app)

#: The groups of the CLI's command tree: ``task``, ``sources``, ... and the
#: subcommands each carries.
_CLI_GROUPS: dict[str, frozenset[str]] = {
    name: frozenset(command.commands)
    for name, command in _CLI_ROOT.commands.items()
    if hasattr(command, "commands")
}

#: The CLI's top-level commands: ``init``, ``doctor``, ``serve``.
_CLI_LEAVES: frozenset[str] = frozenset(
    name for name, command in _CLI_ROOT.commands.items() if not hasattr(command, "commands")
)

#: The options of the CLI's root that take a value, so a value is not read
#: as a command word. Read from the application rather than written down.
_CLI_VALUE_OPTIONS: frozenset[str] = frozenset(
    option
    for parameter in _CLI_ROOT.params
    for option in parameter.opts
    if not getattr(parameter, "is_flag", False)
)

#: A word that can be a command's own word: the README gate's rule, so the
#: two gates agree on where a command name ends.
_COMMAND_WORD_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9-]*$")

#: What a step of the walk names: the walk's own material folder, or the walk
#: script that runs the whole path. **These are steps of the walk, not
#: maintained commands**, and they are recognised by what they name rather
#: than by a list kept here.
_WALK_STEP_MARKERS: tuple[str, ...] = ("workspace/materials", "scripts/outsider_path.py")


def _block_lines(text: str) -> list[str]:
    """Every line of a fenced shell block, whitespace collapsed.

    **The walk script's fence pairing, and its rule about comments**: a line
    that starts with ``#`` is a comment and is not a command.
    """
    lines: list[str] = []
    for language, block in WALK_SCRIPT.fenced_blocks(text):
        if language not in SHELL_LANGUAGES:
            continue
        for raw in block:
            collapsed = " ".join(raw.strip().split())
            if collapsed and not raw.strip().startswith("#"):
                lines.append(collapsed)
    return lines


def _inline_spans(text: str) -> list[str]:
    """Every inline code span of a document, whitespace collapsed.

    **The walk script's reader of inline spans**, which leaves the fenced
    blocks out -- a span inside a block is part of the block.
    """
    spans: list[str] = []
    for span in WALK_SCRIPT.inline_code(text):
        spans.append(" ".join(span.strip().split()))
    return spans


def _after_the_script(words: list[str]) -> list[str]:
    """The words of a command line that follow the console script's name.

    The CLI's root options and the values they take are skipped: they say
    *where* the command runs, not *which* command runs.
    """
    if "labcairn" not in words:
        return []
    start = words.index("labcairn") + 1
    while start < len(words) and words[start].startswith("-"):
        if words[start] in _CLI_VALUE_OPTIONS and start + 1 < len(words):
            start += 2
        else:
            start += 1
    return words[start:]


def _command_path(line: str) -> tuple[str, ...] | None:
    """The CLI command path a line names, or ``None`` if it names none.

    The resolution is the CLI's own grammar: the console script's name, then
    the root options, then the command path. ``uv run labcairn --workspace
    ./workspace task status --json`` and ``labcairn task status`` and the
    bare ``task status`` all resolve to ``("task", "status")``.

    **A path the CLI does not have resolves to nothing**, so a document
    cannot smuggle a command past the gate by writing it wrongly.
    """
    words = line.split()
    if not words:
        return None

    after = _after_the_script(words)
    if after:
        first = after[0]
        if first in _CLI_GROUPS:
            if len(after) > 1 and after[1] in _CLI_GROUPS[first]:
                return (first, after[1])
            return None
        if first in _CLI_LEAVES:
            return (first,)
        return None

    # The quickstart's shorthand for a command: a group name and its
    # subcommand, without the script's name.
    if words[0] in _CLI_GROUPS:
        if len(words) > 1 and words[1] in _CLI_GROUPS[words[0]]:
            return (words[0], words[1])
        return None
    if words[0] in _CLI_LEAVES:
        return (words[0],)
    return None


def _names_a_command(line: str) -> bool:
    """Whether a line names a product command at all.

    A line that names the console script and then a command word names a
    command; a line that names the script and nothing else (``labcairn``, or
    ``uv run labcairn --help``) names the program, not a command.
    """
    words = line.split()
    if not words:
        return False
    after = _after_the_script(words)
    if after:
        return bool(_COMMAND_WORD_RE.match(after[0]))
    if words[0] in _CLI_GROUPS or words[0] in _CLI_LEAVES:
        return len(words) > 1 and bool(_COMMAND_WORD_RE.match(words[1]))
    return False


def _product_paths(text: str) -> set[tuple[str, ...]]:
    """The CLI command paths a document names.

    **Every line and every span is a candidate**, because the quickstart
    names a command in prose (``task report``) that the README names in a
    table cell (``labcairn task report``), and both are the same command.
    """
    paths: set[tuple[str, ...]] = set()
    for line in (*_block_lines(text), *_inline_spans(text)):
        path = _command_path(line)
        if path is not None:
            paths.add(path)
    return paths


def _unresolved_names(text: str) -> list[str]:
    """The commands a document names that the CLI does not have.

    A line that names a command -- ``labcairn task reconcile``, ``task
    reconcile`` -- and resolves to nothing is a command the CLI does not
    have. The walk script's own reader would have passed it by.
    """
    unresolved: list[str] = []
    for line in (*_block_lines(text), *_inline_spans(text)):
        if _names_a_command(line) and _command_path(line) is None:
            unresolved.append(line)
    return unresolved


def _maintained_commands(repo_root: Path, text: str) -> set[str]:
    """The maintained commands a document shows, as whole lines.

    **The walk script's reader of a document's commands**, which is the one
    every other gate uses, and which leaves the console script's own calls
    to the CLI gate. A line that resolves to a CLI command path is a product
    command, not a maintained one, so it is not counted twice.
    """
    console_scripts = WALK_SCRIPT.console_script_names(repo_root)
    commands: set[str] = set()
    for command in WALK_SCRIPT.readme_commands(text, console_scripts):
        if _command_path(command) is None:
            commands.add(command)
    return commands


def _is_a_walk_step(command: str) -> bool:
    """Whether a command is a step of the walk rather than a maintained one."""
    return any(marker in command for marker in _WALK_STEP_MARKERS)


def _walk_table_commands() -> set[str]:
    """The repository's maintained commands, as the walk script's table holds them."""
    commands: set[str] = set()
    for row in WALK_SCRIPT.README_COMMANDS:
        commands.add(row.documented)
    return commands


def _readme_text(repo_root: Path) -> str:
    return (repo_root / "README.md").read_text(encoding="utf-8")


def _quickstart_text(repo_root: Path) -> str:
    return (repo_root / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The two surfaces, in both directions
# ---------------------------------------------------------------------------


def test_every_command_the_quickstart_shows_the_readme_shows_too(repo_root: Path) -> None:
    """Fail-closed, quickstart side: a command the README does not show fails.

    A reader who follows the quickstart types exactly these commands; a
    command the README never names is a command the README's own witnesses
    never ran.
    """
    readme_paths = _product_paths(_readme_text(repo_root))
    missing = sorted(
        path for path in _product_paths(_quickstart_text(repo_root)) if path not in readme_paths
    )
    assert not missing, (
        f"docs/QUICKSTART.md shows the command(s) {missing}, which README.md "
        "does not show. The quickstart names a command the README does not "
        "document: name it in README.md, or correct the quickstart."
    )


def test_every_command_the_readme_shows_the_quickstart_shows_too(repo_root: Path) -> None:
    """Fail-closed, README side: a command the quickstart does not show fails.

    The other direction of the same claim. A command the README documents and
    the quickstart never walks is not witnessed by the quickstart's own §7
    table.
    """
    quickstart_paths = _product_paths(_quickstart_text(repo_root))
    missing = sorted(
        path for path in _product_paths(_readme_text(repo_root)) if path not in quickstart_paths
    )
    assert not missing, (
        f"README.md shows the command(s) {missing}, which docs/QUICKSTART.md "
        "does not show. The README documents a command the quickstart never "
        "walks: show it in the quickstart, or correct the README."
    )


def test_the_two_documents_show_the_same_maintained_commands(repo_root: Path) -> None:
    """The maintained commands of the two documents are the same set.

    **The walk script's table is the authority**, because that is the table
    the README is already checked against; the two documents are checked
    against it and against each other.

    The quickstart's by-hand path also shows steps of the walk -- making the
    research folder, copying the material into it, running the walk script --
    and those are not maintained commands. They are recognised by what they
    name, so nothing here has to be kept in step with the page.
    """
    table = _walk_table_commands()
    readme = _maintained_commands(repo_root, _readme_text(repo_root))
    quickstart = _maintained_commands(repo_root, _quickstart_text(repo_root))

    unknown_in_readme = sorted(readme - table)
    assert not unknown_in_readme, (
        f"README.md shows the maintained command(s) {unknown_in_readme}, which "
        "scripts/outsider_path.py's table does not carry. Add a row to that "
        "table (and a witness to tests/test_readme_accuracy.py), or remove the "
        "command from the README."
    )

    missing_from_readme = sorted(table - readme)
    assert not missing_from_readme, (
        f"scripts/outsider_path.py's table carries the command(s) "
        f"{missing_from_readme}, which README.md does not show. Show them in "
        "the README, or drop them from that table."
    )

    steps = {command for command in quickstart if _is_a_walk_step(command)}
    unknown_in_quickstart = sorted(quickstart - table - steps)
    assert not unknown_in_quickstart, (
        f"docs/QUICKSTART.md shows the maintained command(s) "
        f"{unknown_in_quickstart}, which neither scripts/outsider_path.py's "
        "table nor README.md carries. Show the command in the README and in "
        "that table, or correct the quickstart."
    )

    missing_from_quickstart = sorted((table - steps) - quickstart)
    assert not missing_from_quickstart, (
        f"scripts/outsider_path.py's table carries the command(s) "
        f"{missing_from_quickstart}, which docs/QUICKSTART.md does not show. "
        "Show them in the quickstart's §7 table, or drop them from that "
        "table."
    )


def test_neither_document_names_a_command_the_cli_does_not_have(repo_root: Path) -> None:
    """A command either document names is a command the CLI has.

    The CLI is the authority on which commands exist. A document that names
    a command the CLI does not have is a reader sent to a command that is
    not there -- and the walk script's reader would have passed it by,
    because it reads a command line without asking the CLI whether the
    command exists.
    """
    unresolved = {
        "README.md": _unresolved_names(_readme_text(repo_root)),
        "docs/QUICKSTART.md": _unresolved_names(_quickstart_text(repo_root)),
    }
    offenders = {name: lines for name, lines in unresolved.items() if lines}
    assert not offenders, (
        "these documents name commands the CLI does not have: "
        f"{offenders}. The command tree is the authority on what exists; "
        "correct the spelling, or drop the command."
    )


# ---------------------------------------------------------------------------
# The reader itself
# ---------------------------------------------------------------------------


def test_the_reader_finds_the_commands_of_both_documents(repo_root: Path) -> None:
    """Guards the extraction against a silent emptiness.

    A reader that finds nothing makes every comparison above vacuously true,
    so the two documents are checked to yield the commands they are known to
    name, and to yield a maintained surface that is not empty.
    """
    readme_paths = _product_paths(_readme_text(repo_root))
    quickstart_paths = _product_paths(_quickstart_text(repo_root))

    assert ("task", "status") in readme_paths, (
        "the reader found no `labcairn task status` in README.md; the "
        "extraction has stopped reading the document"
    )
    assert ("task", "status") in quickstart_paths, (
        "the reader found no `task status` in docs/QUICKSTART.md; the "
        "extraction has stopped reading the document"
    )
    assert len(readme_paths) >= 10, (
        f"the reader found only {len(readme_paths)} command path(s) in "
        "README.md; a broken reader would make the comparisons vacuous"
    )
    assert len(quickstart_paths) >= 10, (
        f"the reader found only {len(quickstart_paths)} command path(s) in "
        "docs/QUICKSTART.md; a broken reader would make the comparisons "
        "vacuous"
    )
    assert _maintained_commands(repo_root, _readme_text(repo_root)), (
        "the reader found no maintained command in README.md"
    )
    assert _maintained_commands(repo_root, _quickstart_text(repo_root)), (
        "the reader found no maintained command in docs/QUICKSTART.md"
    )


def test_the_gate_reads_with_the_walk_scripts_reader(repo_root: Path) -> None:
    """One reader, not two -- checked on the reader itself.

    Two extractors can agree on today's documents and differ on tomorrow's.
    The walk script pairs its fences fence by fence, and a pattern-based
    reader here would read the prose between two shell blocks as a command.
    """
    assert WALK_SCRIPT.readme_commands is not None, "the walk script's reader is missing"
    assert WALK_SCRIPT.inline_code is not None, "the walk script's span reader is missing"
    for text in (_readme_text(repo_root), _quickstart_text(repo_root)):
        assert _block_lines(text), (
            "the reader found no fenced shell block in a document that has one"
        )
        assert _inline_spans(text), (
            "the reader found no inline code span in a document that has one"
        )
