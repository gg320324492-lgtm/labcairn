"""Every refusal the CLI raises, watched by construction rather than by count.

Gate G4's independent review counted the refusals by hand and got the count
wrong: the sweep named fifteen of the twenty-three refusal branches the three
surfaces own, and six of the eight it missed survived the whole test suite.
**A table counted by hand is wrong the moment the code moves**, so the remedy
cannot be six more witnesses; it has to be an enumeration that cannot be got
wrong by hand.

This file is that enumeration. It:

* **parses** the CLI's package and finds every site that refuses: a ``raise``
  of one of the exception classes the CLI defines for itself, and a call to
  the CLI's own ``_refuse`` helper — the CLI's own refusal vocabulary,
  *found* rather than listed;
* **resolves** each site's message into its **runs**: the literal words the
  product writes, with the values it interpolates left out, so that what a
  witness has to quote is the product's own words and not a paraphrase of
  them;
* **reads the test suite** and collects every string a test compares about a
  refusal, together with the values it compares them with; and
* **matches** them, requiring that every refusal has a witness of its own, and
  that no two refusals share one.

**The granularity is the test, not the file.** A witness is a whole test, and
a test is a candidate only when *that test* reaches the CLI — it imports the
CLI, or it uses the CLI's own rig. The file a test lives in is only the outer
bound: **one import anywhere in a file used to make every test in that file a
candidate**, and two candidates chasing one refusal leave that refusal with no
witness at all — the gate goes red on a tree where nothing about the product
changed.

**Two refusals can say the same sentence, and then the sentence cannot say
which refusal a witness watches.** The configuration that cannot be read and
the policy that cannot be read say the same three words; the module's refusal
for a source root outside the workspace and the command's refusal for the same
condition say the same words too. **A witness is bound to a refusal by the
value that refusal names** — the configuration's path, the policy's path, the
providers file's path — so that a witness of the configuration's refusal
cannot answer for the policy's. Where the value cannot tell two refusals
apart either, the pairing is **written down** in :data:`WATCHED_BY` and
checked: the witness must exist in the suite, must compare a phrase the
refusal says, and every witness the derivation offers must be written down.

**Nothing here is a list of refusals.** A refusal added to the product is
noticed by this test whether or not anyone remembers to come here and add a
witness; a witness removed is noticed too — the witness this enumeration
names for a refusal, and the other tests the record names.

**The boundary is the CLI's own refusals, and it is stated rather than
assumed.** Every refusal the CLI raises is required to have a witness, with
two kinds of exception:

* a refusal that carries **no words of the CLI's own** — a message that is
  only ``str(error)`` — is another component's refusal passing through, and
  a witness for it would be a witness of that component's words. The
  enumeration finds those by itself: it is the same rule that says a refusal
  must say something.
* a refusal raised in a handler for **a failure no single invocation of the
  CLI can produce** is a branch no test can reach. Those are listed by the
  failure they handle and not by the refusal they raise, so that a new
  refusal in the same handler is found by the enumeration rather than
  forgotten by it, and a list that goes stale says so.

**The API's five refusals** are watched by their *reason* in
``tests/test_api.py``, not by a sentence of their message, and are out of
scope here for the same reason: they are the API's words, not the CLI's.
"""

from __future__ import annotations

import ast
import builtins
import re
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest
from refusal_witnesses import compared_texts

pytestmark = pytest.mark.negative

#: The repository's root, found from this file.
REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: The CLI's own package — the surface whose refusals are enumerated here.
CLI_PACKAGE: Final[Path] = REPOSITORY_ROOT / "src" / "labcairn" / "cli"

#: Where the CLI declares its refusal reasons.
CLI_MODELS: Final[Path] = CLI_PACKAGE / "models.py"

#: The project's own manifest, where the CLI's console script is declared.
PROJECT_MANIFEST: Final[Path] = REPOSITORY_ROOT / "pyproject.toml"

#: The tests, which is where the witnesses are.
TESTS_DIRECTORY: Final[Path] = REPOSITORY_ROOT / "tests"

#: The fewest words a witness must quote.
#:
#: A witness quotes a **phrase**, not a word. "workspace" is in half the
#: CLI's messages and names none of them; "could not be read as JSON" names
#: one. Three words is the shortest phrase a reader can hold against the
#: message it claims to be watching.
MINIMUM_WORDS: Final[int] = 3

#: The fewest words a run of a message has to have to count as a phrase.
#:
#: A message is written in runs, and a run can be a punctuation mark — the
#: ": " between two interpolated values is a run of its own. Such a run is
#: in half the messages and names none of them, so it is not a phrase and
#: does not count. Two words is the shortest run that says something.
MINIMUM_RUN_WORDS: Final[int] = 2

#: The failures a single invocation of the CLI cannot produce.
#:
#: A refusal raised in a handler for one of these is a branch no test can
#: reach: the database's own migrations are missing only in an installation
#: that is broken, and the interpreter's exit reaches the CLI only after a
#: race between the port check and the bind.
#:
#: **They are listed by the failure they handle and not by the refusal they
#: raise**, so a new refusal in the same handler is found by the
#: enumeration rather than forgotten by it, and
#: :func:`test_the_failures_that_cannot_happen_are_still_there` says so when
#: the list goes stale.
UNREACHABLE_FAILURES: Final[frozenset[str]] = frozenset(
    {"MigrationsUnavailableError", "SystemExit"}
)


@dataclass(frozen=True, slots=True)
class Refusal:
    """One site in the CLI that refuses, and the words its refusal is made of.

    ``pieces`` are the literal runs of the message — the words the product
    writes, in the order it writes them, with the values it interpolates
    left out. The list is empty when the message is not literal text: a
    refusal that hands another component's words on has no words of its own,
    and is not a refusal this enumeration can hold a witness against.

    ``values`` are the values the message interpolates, written as the
    product writes them — ``location.config_path`` for the configuration's
    refusal, ``location.policy_path`` for the policy's. **They are what tells
    two refusals that say the same words apart**, and they are read from the
    product's own source, so a witness that compares the configuration's path
    cannot be the witness of the policy's refusal.

    ``handled`` names the failures whose handler the refusal is raised in.
    """

    path: Path
    line: int
    kind: str
    pieces: tuple[str, ...]
    function: str = ""
    handled: tuple[str, ...] = ()
    values: tuple[str, ...] = ()

    @property
    def place(self) -> str:
        """Where the refusal is, as a reader would name it."""
        return f"{self.path.relative_to(REPOSITORY_ROOT).as_posix()}:{self.line}"

    @property
    def words(self) -> str:
        """The refusal's words, with the values left out."""
        return " ".join(piece for piece in self.pieces if piece)

    @property
    def watches(self) -> bool:
        """Whether this enumeration requires a witness of this refusal.

        It does, unless the refusal carries no words of the CLI's own — it
        is another component's refusal passing through — or it is raised in
        a handler for a failure no single invocation of the CLI can produce.
        """
        if not self.pieces:
            return False
        return not any(failure in UNREACHABLE_FAILURES for failure in self.handled)


@dataclass(frozen=True, slots=True)
class Witness:
    """One test, and the words it compares about a refusal.

    **One test is one witness.** A witness is a whole test — the
    expectations it states together — and not each string in it, so a test
    that compares two refusals' words is the witness of one of them and
    cannot be the witness of both.

    ``values`` are the values the test interpolates into what it compares,
    written as the test writes them. They are what bind a witness to a
    refusal: the test that compares ``location.config_path`` is the witness
    of the refusal that names the configuration's path.
    """

    path: Path
    function: str
    texts: tuple[str, ...]
    values: tuple[str, ...]

    @property
    def place(self) -> str:
        """Where the witness is, as a reader would name it."""
        return f"{self.path.relative_to(REPOSITORY_ROOT).as_posix()}::{self.function}"


# --------------------------------------------------------------------------- #
# reading the product
# --------------------------------------------------------------------------- #


def _modules(package: Path) -> list[Path]:
    """The Python modules in *package*."""
    return sorted(package.rglob("*.py"))


def _read(path: Path) -> str:
    """The text of the file at *path*.

    **The seam the mechanism's own witnesses are driven through.** The gate
    reads the product's sources and the suite's, and a witness that checks
    what the gate does with a source the tree does not hold writes the
    source here and lets the gate read it. The seam is one function wide,
    so that reading the source is the only thing a witness replaces.
    """
    return path.read_text(encoding="utf-8")


def _parse(path: Path) -> ast.Module:
    """The syntax tree of the file at *path*."""
    return ast.parse(_read(path), filename=str(path))


def _sources_text() -> str:
    """Every line of the CLI's own sources, joined.

    Read so that a second opinion on what the sources say can be had without
    a parser: the text is what a reader would count.
    """
    return "\n".join(path.read_text(encoding="utf-8") for path in _modules(CLI_PACKAGE))


def _is_exception(name: str) -> bool:
    """Whether *name* is one of the interpreter's own exception classes."""
    candidate = getattr(builtins, name, None)
    if not isinstance(candidate, type):
        return False
    return issubclass(candidate, BaseException)


def _refusal_classes() -> dict[str, Path]:
    """The exception classes the CLI defines for itself.

    **A surface's own exception classes are its refusals.** The CLI raises
    ``WorkspaceSetupError`` before the layer is reached, and the API's and the
    layer's classes belong to their own packages and are watched there. The
    classes are found by reading the package, so a new one is noticed here
    rather than needing to be added to a list.
    """
    classes: dict[str, Path] = {}
    for path in _modules(CLI_PACKAGE):
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Error"):
                continue
            bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
            if any(_is_exception(base) for base in bases):
                classes[node.name] = path
    return classes


def _called_name(call: ast.Call) -> str:
    """The name the call is written under."""
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _source_text(node: ast.AST) -> str:
    """The source text of *node*."""
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - unparse does not fail on a parsed tree
        return ""


def _bindings(function: ast.FunctionDef) -> dict[str, ast.expr]:
    """The expressions the names in *function* are bound to.

    **A binding is read, not guessed at.** The policy's refusal interpolates
    ``path``, and ``path`` is the policy file's path — ``location.policy_path``
    — so the refusal is read as naming the policy and not as naming a name.
    """
    bindings: dict[str, ast.expr] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            bindings[target.id] = node.value
    return bindings


def _module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    """The names a module binds at its top level, and the expressions they hold.

    **A constant at the module's top level is a message like any other.**
    The product may hoist a refusal's words into one, and the words are the
    same words; the rule that reads them must not depend on where the
    product happened to write them.
    """
    bindings: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            bindings[node.target.id] = node.value
    return bindings


@dataclass(frozen=True, slots=True)
class _Scope:
    """The names a message can be written through.

    **A message says the same words however it is written.** A refusal's
    message may be a literal, an interpolated string, a call to a function
    of the same module — or a *name*, bound in the enclosing function or at
    the module's top level. The scope is where a name is looked up, so that
    the rule for reading a message is one rule and not one for a literal and
    another for a name.
    """

    functions: dict[str, ast.FunctionDef]
    function_bindings: dict[str, ast.expr]
    module_bindings: dict[str, ast.expr]

    @property
    def bindings(self) -> dict[str, ast.expr]:
        """The names in scope, the enclosing function's own first."""
        return {**self.module_bindings, **self.function_bindings}

    def bound(self, name: str) -> ast.expr | None:
        """The expression a name is bound to, if it is bound at all."""
        if name in self.function_bindings:
            return self.function_bindings[name]
        return self.module_bindings.get(name)

    def inside(self, function: ast.FunctionDef) -> _Scope:
        """The scope of a function of the same module."""
        return _Scope(self.functions, _bindings(function), self.module_bindings)


def _value_text(node: ast.expr, bindings: dict[str, ast.expr]) -> str:
    """The source text of the value *node* names."""
    if isinstance(node, ast.Name) and node.id in bindings:
        return _source_text(bindings[node.id])
    return _source_text(node)


def _pieces(
    expression: ast.expr | None,
    scope: _Scope,
    seen: frozenset[str] = frozenset(),
    named: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """The literal runs a message is made of, with the values left out.

    A message is read as a **template**: the literal text the product
    writes, with each interpolated value left out. A witness quotes the
    literal text and may fill the values in — the policy file's refusal says
    *which* file could not be read, and the witness says the same three
    words with its own path in them — so a witness is a fragment of the
    template rather than of one rendering of it.

    **A message is a word, however it is written.** It may be a literal, an
    interpolated string, a name bound to one of those, or a call to a
    function of the same module — and a name is read through the bindings
    the values are read through, so that the rule for the word is one rule
    and not two. A message the product hoisted into a constant says the
    words it always said, and it stays in the watch set: **the syntax of a
    message cannot decide whether it is watched.**
    """
    if expression is None:
        return ()
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return (expression.value,)
    if isinstance(expression, ast.JoinedStr):
        return tuple(
            value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else ""
            for value in expression.values
        )
    if isinstance(expression, ast.Call):
        name = _called_name(expression)
        function = scope.functions.get(name)
        if function is not None and name not in seen:
            inner = scope.inside(function)
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    return _pieces(node.value, inner, seen | {name}, named)
        return ()
    if isinstance(expression, ast.Name):
        bound = scope.bound(expression.id)
        if bound is not None and expression.id not in named:
            return _pieces(bound, scope, seen, named | {expression.id})
        return ()
    return ()


def _values(
    expression: ast.expr | None,
    scope: _Scope,
    seen: frozenset[str] = frozenset(),
    named: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """The values a message interpolates, as the product writes them.

    **The values are what tell two refusals that say the same words apart.**
    The configuration that cannot be read and the policy that cannot be read
    say the same three words; what separates them is the path each of them
    names, and a witness that compares the configuration's path is the
    witness of the configuration's refusal and not of the policy's.

    **The values are read through the same scope as the words**, so a
    message the product hoisted into a constant is read whole: the words
    it writes and the values it puts in them.
    """
    if expression is None:
        return ()
    if isinstance(expression, ast.JoinedStr):
        return tuple(
            _value_text(value.value, scope.bindings)
            for value in expression.values
            if isinstance(value, ast.FormattedValue)
        )
    if isinstance(expression, ast.Call):
        name = _called_name(expression)
        function = scope.functions.get(name)
        if function is not None and name not in seen:
            inner = scope.inside(function)
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    return _values(node.value, inner, seen | {name}, named)
        return ()
    if isinstance(expression, ast.Name):
        bound = scope.bound(expression.id)
        if bound is not None and expression.id not in named:
            return _values(bound, scope, seen, named | {expression.id})
        return ()
    return ()


def _exception_names(expression: ast.expr | None) -> tuple[str, ...]:
    """The names of the failures an ``except`` clause handles."""
    if expression is None:
        return ()
    if isinstance(expression, ast.Name):
        return (expression.id,)
    if isinstance(expression, ast.Tuple):
        return tuple(element.id for element in expression.elts if isinstance(element, ast.Name))
    return ()


def _handler_failures(tree: ast.Module) -> dict[int, tuple[str, ...]]:
    """The failures handled where each of the CLI's refusals is raised.

    Keyed by the identity of the refusal's call. A refusal raised in a
    handler for a failure the CLI cannot itself produce is a branch no test
    can reach, and the enumeration says so rather than asking for a witness
    that cannot exist.
    """
    failures: dict[int, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            names = _exception_names(handler.type)
            for child in ast.walk(handler):
                if isinstance(child, ast.Call) and _called_name(child) == "_refuse":
                    failures[id(child)] = names
    return failures


def _enclosing_function(functions: list[ast.FunctionDef], line: int) -> str:
    """The name of the innermost function the line is in."""
    owners = [
        function
        for function in functions
        if function.lineno <= line <= (function.end_lineno or function.lineno)
    ]
    if not owners:
        return "<module>"
    innermost = min(owners, key=lambda function: function.end_lineno or function.lineno)
    return innermost.name


def _refusals() -> list[Refusal]:
    """Every refusal the CLI raises, and the words each one is made of.

    Two shapes of refusal are read: a ``raise`` of one of the CLI's own
    exception classes, and a call to the CLI's own ``_refuse`` helper. Both
    are the CLI's own vocabulary, and both are required to have a witness.
    """
    classes = _refusal_classes()
    found: list[Refusal] = []
    for path in _modules(CLI_PACKAGE):
        tree = _parse(path)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        every_function = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        constants = _module_constants(tree)
        handled = _handler_failures(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                name = _called_name(node.exc)
                if name in classes:
                    message = node.exc.args[0] if node.exc.args else None
                    scope = _Scope(
                        functions,
                        _bindings_of(every_function, node.lineno),
                        constants,
                    )
                    found.append(
                        Refusal(
                            path,
                            node.lineno,
                            "raise",
                            _pieces(message, scope),
                            _enclosing_function(every_function, node.lineno),
                            (),
                            _values(message, scope),
                        )
                    )
            elif isinstance(node, ast.Call) and _called_name(node) == "_refuse":
                message = node.args[1] if len(node.args) > 1 else None
                scope = _Scope(
                    functions,
                    _bindings_of(every_function, node.lineno),
                    constants,
                )
                found.append(
                    Refusal(
                        path,
                        node.lineno,
                        "_refuse",
                        _pieces(message, scope),
                        _enclosing_function(every_function, node.lineno),
                        handled.get(id(node), ()),
                        _values(message, scope),
                    )
                )
    return sorted(found, key=lambda refusal: (str(refusal.path), refusal.line))


def _bindings_of(functions: list[ast.FunctionDef], line: int) -> dict[str, ast.expr]:
    """The bindings of the innermost function the line is in."""
    owners = [
        function
        for function in functions
        if function.lineno <= line <= (function.end_lineno or function.lineno)
    ]
    if not owners:
        return {}
    innermost = min(owners, key=lambda function: function.end_lineno or function.lineno)
    return _bindings(innermost)


# --------------------------------------------------------------------------- #
# reading the witnesses
# --------------------------------------------------------------------------- #


def _cli_refusal_reasons() -> set[str]:
    """The reasons the CLI gives its refusals, read from the CLI's own models."""
    reasons: set[str] = set()
    for node in ast.walk(_parse(CLI_MODELS)):
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.startswith("CLI_REFUSAL_"):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            reasons.add(node.value.value)
    return reasons


def _imports_the_cli(node: ast.AST) -> bool:
    """Whether *node* imports the CLI.

    **The CLI's own package, wherever the import is written.** A test that
    imports it inside its own body reaches the CLI as surely as one that
    imports it at the top of the file, and the difference matters: the
    import is what the test reaches the CLI *through*, not what the file it
    lives in happens to hold.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.ImportFrom):
            if child.module is not None and child.module.startswith("labcairn.cli"):
                return True
        elif isinstance(child, ast.Import) and any(
            alias.name.startswith("labcairn.cli") for alias in child.names
        ):
            return True
    return False


def _holds_a_reason(node: ast.AST, reasons: set[str]) -> bool:
    """Whether *node* says one of the CLI's refusal reasons.

    **The reasons are the CLI's vocabulary, and quoting them is not
    reaching the CLI.** A test that holds a reason is not thereby a test
    that ran the CLI, and the rule that decides candidacy does not ask
    this. It is asked here, by the witness that shows what the rule cost:
    a test that quotes a reason and reaches nothing is not a candidate,
    and the witness says so by showing the reason is there.
    """
    return any(
        isinstance(child, ast.Constant) and child.value in reasons for child in ast.walk(node)
    )


def _witness_modules() -> list[Path]:
    """The test modules that watch the CLI's refusals.

    **A module watches the CLI's refusals if it imports the CLI.** The
    import is the outer bound: the scan reads the modules that import the
    CLI, and a module that does not import it is not read.

    **The outer bound is a bound, and it is known to be one.** A module
    that reaches the CLI only through another module's rig is not read,
    and the tests in it are not candidates — the limit of the file
    granularity, recorded in ``docs/handoff/CURRENT.md``. Widening the
    bound is a change to the set of candidates rather than to a filter,
    and it is not made here.

    **The module is the outer bound, and the test decides within it.**
    :func:`_witnesses` asks each test whether it reaches the CLI, because
    one import anywhere in a file makes every test in that file a candidate
    otherwise — and two candidates chasing one refusal leave that refusal
    with no witness at all.
    """
    modules: list[Path] = []
    for path in sorted(TESTS_DIRECTORY.rglob("test_*.py")):
        if path.resolve() == Path(__file__).resolve():
            # This file does not witness itself. Its own strings are the
            # machinery's, not a product's.
            continue
        tree = _parse(path)
        if _imports_the_cli(tree):
            modules.append(path)
    return modules


def _witnesses(module: ast.Module, path: Path) -> list[Witness]:
    """Every witness a module holds, one per test.

    **A witness's text is what the test compares.** The rule is the shared
    one, in :mod:`tests.refusal_witnesses`, and it is the same rule the
    ledger in ``tests/test_cli_workspace_refusals.py`` uses, so the two
    enumerations cannot drift apart on what a witness is.

    **A witness's value is what it interpolates into what it compares.** The
    values are read out of the test's own source, and they are what bind a
    witness to a refusal: the test that compares the configuration's path
    cannot be the witness of the policy's refusal.

    **A test that does not reach the CLI is not a witness of it.** The
    module is only the outer bound: the test itself has to import the CLI,
    or to use the CLI's own rig. A test in the API's file that asserts the
    sentence the CLI's door also writes is about the API's door, and it must
    not be counted as a second candidate for the CLI's — two candidates
    chasing one refusal leave that refusal with no witness at all.
    """
    witnesses: list[Witness] = []
    for function in [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)]:
        texts = tuple(compared_texts(function))
        if not texts:
            continue
        if not _witness_reaches_the_cli(function, path.stem):
            continue
        witnesses.append(Witness(path, function.name, texts, _witness_values(function)))
    return witnesses


# --------------------------------------------------------------------------- #
# reading what reaches the CLI
#
# **A test is a candidate because it reaches the CLI, and the reach is read
# out of the tree rather than asserted.** Two ways a test reaches it: it
# imports the CLI itself; and it uses a name its module bound to the CLI —
# the rig the module reaches the CLI through, whether that rig imports the
# CLI's package or runs the CLI's program.
#
# **The last is the rig, and the rig is followed.** A CLI test often says
# nothing of the CLI's own: it calls a helper that runs the console script
# and compares what the script printed. The helper reaches the CLI, so the
# test does too — and a helper that reaches the CLI is found by following
# what the helper uses, name by name, until the CLI is reached or the names
# run out.
#
# **A refusal reason is not a way of reaching the CLI.** The reasons are
# vocabulary the CLI shares with the rest of the product, and the second
# reader's measurement was a test that quoted one and reached nothing: it
# was made a candidate, and the gate went red on a tree whose product had
# not changed.
# --------------------------------------------------------------------------- #


def _program_names() -> frozenset[str]:
    """The names the CLI's console script is installed under.

    **Read from the project's own manifest**, under ``[project.scripts]``,
    so the name is the product's and not a list: a test that runs that
    program runs the CLI, and the Windows name carries the extension the
    installer gives it.
    """
    names: set[str] = set()
    in_scripts = False
    for line in PROJECT_MANIFEST.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_scripts = stripped == "[project.scripts]"
            continue
        if not in_scripts or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        names.add(name)
        names.add(f"{name}.exe")
    return frozenset(names)


#: The test modules read once each, by name.
#:
#: A module that borrows another's rig — ``from test_cli_support import
#: workspace`` — reaches the CLI through the module it borrows from, so a
#: name has to be resolved in the module it came from.
_TREES: dict[str, ast.Module] = {}

#: The names each module binds at its top level, read once.
_BINDINGS: dict[str, dict[str, ast.AST]] = {}

#: The names each binding uses, and the strings it holds, read once.
_USES: dict[tuple[str, str], frozenset[str]] = {}
_HOLDS: dict[tuple[str, str], frozenset[str]] = {}

#: Whether a binding imports the CLI, read once.
_IMPORTS: dict[tuple[str, str], bool] = {}

#: The names that reach the CLI, read once.
#:
#: **Only the ones that do.** A name that does not reach the CLI may look
#: as though it does when the names are followed through a cycle, so a
#: negative is asked again rather than remembered.
_REACHES: dict[tuple[str, str], bool] = {}

#: The tests that reach the CLI, read once.
_TEST_REACHES: dict[tuple[str, str, int], bool] = {}


def _tree_of(module: str) -> ast.Module | None:
    """The tree of the test module named *module*, if the suite holds one."""
    if module not in _TREES:
        path = TESTS_DIRECTORY / f"{module}.py"
        if not path.is_file():
            return None
        _TREES[module] = _parse(path)
    return _TREES[module]


def _module_bindings(module: str) -> dict[str, ast.AST]:
    """The names a module binds at its top level, and what it binds them to.

    **Read once per module**, because the reachability of a name is asked
    of the same bindings again and again — once for every test that uses
    the name.
    """
    if module not in _BINDINGS:
        _BINDINGS[module] = _top_level_bindings(_tree_of(module))
    return _BINDINGS[module]


def _top_level_bindings(tree: ast.Module | None) -> dict[str, ast.AST]:
    """The names a module binds at its top level, and what it binds them to."""
    bindings: dict[str, ast.AST] = {}
    if tree is None:
        return bindings
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = node
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[node.name] = node
    return bindings


def _names(node: ast.AST) -> frozenset[str]:
    """The names *node* uses."""
    return frozenset(child.id for child in ast.walk(node) if isinstance(child, ast.Name))


def _strings(node: ast.AST) -> frozenset[str]:
    """The strings *node* holds, without the prose among them.

    **A docstring is not a string the code acts on.** A docstring that
    names the CLI's program says so in prose; the rig that *runs* the
    program holds the name in code, and that is what reaches the CLI.
    """
    prose = {
        id(child.value)
        for child in ast.walk(node)
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant)
    }
    return frozenset(
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and id(child) not in prose
    )


def _uses_of(module: str, name: str, node: ast.AST) -> frozenset[str]:
    """The names the binding *name* of *module* uses."""
    key = (module, name)
    if key not in _USES:
        _USES[key] = _names(node)
    return _USES[key]


def _holds_of(module: str, name: str, node: ast.AST) -> frozenset[str]:
    """The strings the binding *name* of *module* holds."""
    key = (module, name)
    if key not in _HOLDS:
        _HOLDS[key] = _strings(node)
    return _HOLDS[key]


def _reaches_the_cli(
    name: str,
    module: str,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> bool:
    """Whether a name a module binds at its top level reaches the CLI.

    **Three ways a name reaches the CLI.** It is bound to the CLI itself —
    an import of ``labcairn.cli`` — or it is bound to something that does:
    a helper that calls the CLI, or a rig that runs the CLI's program. The
    last is the way the CLI is reached as a *program* rather than as a
    package, and it is recognised by the name the project's own manifest
    gives the console script.

    **A name borrowed from another test module is resolved there.** The rig
    a CLI test uses often lives in the module that owns it, and the borrow
    is the only thing that connects the two.
    """
    if (module, name) in seen:
        return False
    seen = seen | {(module, name)}
    if _REACHES.get((module, name)):
        return True
    binding = _module_bindings(module).get(name)
    if binding is None:
        return False
    if isinstance(binding, ast.ImportFrom):
        if binding.module is not None and binding.module.startswith("labcairn.cli"):
            return True
        if binding.module is None or _tree_of(binding.module) is None:
            return False
        alias = next(
            (one for one in binding.names if (one.asname or one.name) == name),
            None,
        )
        if alias is None or alias.name == "*":
            return False
        reached = _reaches_the_cli(alias.name, binding.module, seen)
    elif isinstance(binding, ast.Import):
        reached = any(alias.name.startswith("labcairn.cli") for alias in binding.names)
    elif isinstance(binding, ast.Assign):
        reached = _reaches_the_cli_in(binding.value, module, name, seen)
    else:
        reached = _reaches_the_cli_in(binding, module, name, seen)
    if reached:
        _REACHES[(module, name)] = True
    return reached


def _reaches_the_cli_in(
    node: ast.AST,
    module: str,
    name: str,
    seen: frozenset[tuple[str, str]],
) -> bool:
    """Whether the code a name is bound to reaches the CLI."""
    key = (module, name)
    if key not in _IMPORTS:
        _IMPORTS[key] = _imports_the_cli(node)
    if _IMPORTS[key]:
        return True
    if _holds_of(module, name, node) & _program_names():
        return True
    return any(_reaches_the_cli(used, module, seen) for used in _uses_of(module, name, node))


def _witness_reaches_the_cli(function: ast.FunctionDef, module: str) -> bool:
    """Whether a test reaches the CLI.

    **Two ways a test reaches it.** It imports the CLI itself; and it uses
    a name its module bound to the CLI — the rig the module reaches the CLI
    through, and the fixture the test takes.

    **A reason the CLI gives its refusals is not a way of reaching it.**
    The reasons are a vocabulary the CLI shares with the rest of the
    product, and a test that quotes one is not thereby a test that ran the
    CLI. The second reader's measurement was a test that named a reason
    and reached nothing: it became a candidate, a refusal that interpolates
    no value could not be told from it, and the gate went red on a tree
    whose product had not changed. **A candidate is a test that reaches
    the CLI, so only a test that reaches the CLI can be one.**
    """
    key = (module, function.name, function.lineno)
    if key in _TEST_REACHES:
        return _TEST_REACHES[key]
    reached = _imports_the_cli(function)
    if not reached:
        for used in _names(function):
            if _reaches_the_cli(used, module):
                reached = True
                break
    if not reached:
        for argument in (*function.args.args, *function.args.kwonlyargs):
            if _reaches_the_cli(argument.arg, module):
                reached = True
                break
    _TEST_REACHES[key] = reached
    return reached


def _witness_values(function: ast.FunctionDef) -> tuple[str, ...]:
    """The values the witness compares, as the witness writes them.

    **Only what the witness compares counts.** A value in a string the test
    merely holds is not compared, and a witness that holds the refusal's
    path without comparing it names nothing — which is the same rule the
    shared module applies to the words, applied to the values.
    """
    bindings = _bindings(function)
    values: list[str] = []
    for statement in ast.walk(function):
        if not isinstance(statement, ast.Assert):
            continue
        for child in ast.walk(statement):
            if isinstance(child, ast.JoinedStr):
                values.extend(_joined_values(child, bindings))
            elif isinstance(child, ast.Name):
                bound = bindings.get(child.id)
                if isinstance(bound, ast.JoinedStr):
                    values.extend(_joined_values(bound, bindings))
    return tuple(dict.fromkeys(values))


def _joined_values(joined: ast.JoinedStr, bindings: dict[str, ast.expr]) -> list[str]:
    """The values one interpolated string names."""
    return [
        _value_text(value.value, bindings)
        for value in joined.values
        if isinstance(value, ast.FormattedValue)
    ]


# --------------------------------------------------------------------------- #
# matching
# --------------------------------------------------------------------------- #


def _phrases(runs: tuple[str, ...]) -> list[str]:
    """The runs of a message that are phrases.

    A run of a message is a piece of the literal text the product writes.
    Some of them are a punctuation mark rather than a phrase — the ": "
    between two interpolated values — and such a run is in half the
    messages and names none of them.
    """
    return [run for run in runs if len(_words(run)) >= MINIMUM_RUN_WORDS]


def _words(text: str) -> list[str]:
    """The words a piece of text says."""
    return [word for word in text.split() if any(character.isalnum() for character in word)]


def _groups(refusals: list[Refusal]) -> dict[tuple[str, ...], list[int]]:
    """The refusals that say the same words, gathered by their index.

    Two refusals whose messages are made of the same literal words are told
    apart by the value each of them interpolates — the configuration's path
    and the policy's path are the same three words with different files in
    them — so they are one group for the purpose of deciding whether a
    witness is *distinctive*.
    """
    groups: dict[tuple[str, ...], list[int]] = {}
    for index, refusal in enumerate(refusals):
        if refusal.pieces:
            groups.setdefault(refusal.pieces, []).append(index)
    return groups


def _owned_phrases(
    refusals: list[Refusal], groups: dict[tuple[str, ...], list[int]]
) -> dict[tuple[str, ...], list[str]]:
    """The phrases each group of refusals says and no other group does.

    **A phrase is owned by a group when no other group's message contains
    it.** "does not exist, so" belongs to the configuration's refusal and to
    nothing else; "which is not a directory" belongs to two — the
    configuration's source root and the command's — and so names neither.
    """
    runs: dict[tuple[str, ...], list[str]] = {}
    for group, members in groups.items():
        runs[group] = list(refusals[members[0]].pieces)
    owned: dict[tuple[str, ...], list[str]] = {}
    for group, members in groups.items():
        phrases = _phrases(refusals[members[0]].pieces)
        owned[group] = [
            phrase
            for phrase in phrases
            if not any(
                phrase in run
                for other, other_runs in runs.items()
                if other != group
                for run in other_runs
            )
        ]
    return owned


def _candidates(
    witnesses: list[Witness],
    refusals: list[Refusal],
    groups: dict[tuple[str, ...], list[int]],
) -> dict[int, list[int]]:
    """Which witnesses could watch which refusal, by the refusal's index.

    A witness could watch a refusal when it **compares a phrase the refusal
    says and no other group says** — the words are the product's own, and
    they name this refusal's group and not another one's.

    **The candidates are a pool, not a pairing.** Two refusals that say the
    same words share their candidates, and so does every refusal whose phrase
    another refusal also says. :func:`_paired` decides which witness watches
    which refusal.
    """
    owned = _owned_phrases(refusals, groups)
    candidates: dict[int, list[int]] = {}
    for witness_index, witness in enumerate(witnesses):
        for text in witness.texts:
            if len(_words(text)) < MINIMUM_WORDS:
                continue
            spoken_for = {
                group
                for group, phrases in owned.items()
                if any(phrase in text or text in phrase for phrase in phrases)
            }
            if len(spoken_for) != 1:
                # The text names two groups, or none. It watches neither.
                continue
            for member in groups[spoken_for.pop()]:
                offered = candidates.setdefault(member, [])
                if witness_index not in offered:
                    offered.append(witness_index)
    return candidates


def _narrowed(candidates: list[int], refusal: Refusal, witnesses: list[Witness]) -> list[int]:
    """The candidates that name the refusal's own value.

    **The value is what tells two refusals that say the same words apart.**
    The configuration's refusal names the configuration's path and the
    policy's refusal names the policy's; the witness that compares the
    configuration's path is the witness of the configuration's refusal.
    """
    named = set(refusal.values)
    return [
        index
        for index in candidates
        if witnesses[index].values and set(witnesses[index].values) <= named
    ]


def _paired(
    refusals: list[Refusal],
    witnesses: list[Witness],
    candidates: dict[int, list[int]],
    recorded: dict[int, tuple[str, tuple[str, ...]]],
) -> tuple[dict[int, str], dict[int, tuple[str, ...]]]:
    """Name the witness of every refusal, and the other tests that watch it.

    **A refusal has a witness of its own, and a witness watches one
    refusal.** Where the value names the refusal, the value decides; where
    it cannot, the record in :data:`WATCHED_BY` does, and the record is
    checked against the tree and against the product.

    **A witness is named by where it is**, so that two tests called the same
    thing are two witnesses and not one.
    """
    named: dict[int, str] = {}
    additional: dict[int, tuple[str, ...]] = {}
    for index, refusal in enumerate(refusals):
        if not refusal.watches:
            continue
        if index in recorded:
            witness, others = recorded[index]
            named[index] = witness
            additional[index] = others
            continue
        pool = candidates.get(index, [])
        if len(pool) == 1:
            named[index] = witnesses[pool[0]].place
            continue
        narrowed = _narrowed(pool, refusal, witnesses)
        if len(narrowed) == 1:
            named[index] = witnesses[narrowed[0]].place
    return named, additional


# --------------------------------------------------------------------------- #
# the record
# --------------------------------------------------------------------------- #

#: The witness of each refusal whose witness set cannot be derived, and the
#: other tests that watch that refusal too.
#:
#: **A witness is bound to a refusal by the value that refusal names, and
#: where the value cannot tell two refusals apart the pairing is written
#: down here.** Four refusals are in that state:
#:
#: * the module's refusal for a source root outside the workspace and the
#:   command's refusal for the same condition, which say the same words and
#:   name the same root — the module's refusal is a ``WorkspaceSetupError``
#:   and the command's is a ``_refuse``, and the difference between them is
#:   the *reason* the CLI answers with, which no phrase of the message
#:   carries;
#: * the policy rule with no effect and the policy rule with an effect this
#:   build does not know, which one ``raise`` refuses together;
#: * and the source root that is not a directory, which two tests watch.
#:
#: **The first entry is the witness this enumeration names for the refusal,
#: and the rest are the other tests that watch it.** A refusal with two
#: watchers is still watched twice over: the named one is the witness the
#: enumeration says watches it, and the others are watched by it too — the
#: doctor names the module's refusal of a source root outside the workspace
#: because it says the same words, and the command's own test names the
#: command's refusal of the same condition for the same reason.
#:
#: **A witness is named by where it is, not by what it is called.** Two
#: tests in two files can be called the same thing — the API's file and the
#: CLI's file both hold a test that refuses a reason the guidance door
#: cannot keep — and a name alone cannot tell them apart. So a witness is
#: written as ``path::function``, the way :attr:`Witness.place` names it.
#:
#: **The record is checked, not trusted.** Every witness in it must exist in
#: the suite and must compare a phrase its refusal says, and every witness
#: the derivation offers for those refusals must be written down here — so
#: a witness that is added and left out of the record, or one that is
#: removed from the suite, is noticed here.
WATCHED_BY: Final[tuple[tuple[str, str, str, str, tuple[str, ...]], ...]] = (
    (
        "src/labcairn/cli/commands.py",
        "_resolve_source_dirs",
        "outside the workspace",
        "tests/test_cli_workspace_refusals.py::"
        "test_a_source_directory_the_command_names_outside_the_workspace_is_refused",
        ("tests/test_cli_parameters.py::test_a_source_dir_outside_the_workspace_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "_rule_from_mapping",
        'needs an "effect" of allow, ask or deny',
        "tests/test_cli_workspace_refusals.py::test_a_policy_rule_with_no_effect_is_refused",
        (
            "tests/test_cli_workspace_refusals.py::"
            "test_a_policy_rule_with_an_unknown_effect_is_refused",
        ),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "outside the workspace",
        "tests/test_cli_workspace_refusals.py::"
        "test_a_source_directory_outside_the_workspace_is_refused",
        ("tests/test_cli_init_doctor.py::test_doctor_names_a_source_root_outside_the_workspace",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "which is not a directory",
        "tests/test_cli_workspace_refusals.py::"
        "test_a_source_directory_that_is_not_a_directory_is_refused",
        (
            "tests/test_cli_workspace_refusals.py::"
            "test_a_configured_source_directory_that_is_not_a_directory_is_refused",
        ),
    ),
)


def _recorded(refusals: list[Refusal]) -> dict[int, tuple[str, tuple[str, ...]]]:
    """The recorded witness of each refusal, and the others that watch it.

    A refusal is named by **the module it is in**, **the function it is in**
    and **a phrase of the sentence it writes** — the three together name one
    site, because two sites in one function can share a prefix.

    **A witness is recorded by where it is** — ``path::function`` — because a
    name alone cannot say which of two tests called the same thing is meant.
    """
    recorded: dict[int, tuple[str, tuple[str, ...]]] = {}
    for module, function, phrase, witness, others in WATCHED_BY:
        found = [
            index
            for index, refusal in enumerate(refusals)
            if refusal.path.relative_to(REPOSITORY_ROOT).as_posix() == module
            and refusal.function == function
            and phrase in refusal.words
        ]
        assert len(found) == 1, (
            f"the record names a refusal in {module}::{function} that the product "
            f"does not raise, or names more than one: {phrase!r}. The sentence "
            "the site writes has changed, and the record has to be told."
        )
        recorded[found[0]] = (witness, others)
    return recorded


def _suite_witnesses() -> list[Witness]:
    """Every witness the suite holds, one per test.

    **Read once for the whole run**, because the reachability of a test is
    asked of it again by every test that needs the witness list, and the
    answer is the same each time.
    """
    witnesses: list[Witness] = []
    for path in _witness_modules():
        tree = _tree_of(path.stem)
        if tree is None:
            continue
        witnesses.extend(_witnesses(tree, path))
    return witnesses


def _tests_in_the_suite() -> dict[str, Witness]:
    """Every witness the suite holds, by where it is.

    **A witness is found by where it is, not by what it is called.** Two
    tests in two files can share a name, and the file a test lives in is
    what tells them apart.
    """
    return {witness.place: witness for witness in _suite_witnesses()}


def _unwatched_refusals(
    refusals: list[Refusal],
    named: dict[int, str],
    suite: dict[str, Witness],
) -> list[tuple[Refusal, str]]:
    """The refusals the gate reports as having no witness of their own.

    **This is the gate's own condition, written once.** The gate fails on
    what this returns, and the test that checks the gate's teeth asks the
    same question of a tree that has been changed on purpose — so the teeth
    are checked against the condition the gate turns on and not against a
    copy of it.
    """
    return [
        (refusals[index], named.get(index, ""))
        for index in range(len(refusals))
        if refusals[index].watches and (index not in named or named[index] not in suite)
    ]


# --------------------------------------------------------------------------- #
# the enumeration
# --------------------------------------------------------------------------- #


def test_every_refusal_the_cli_raises_has_a_witness_of_its_own() -> None:
    """Every refusal the CLI raises is watched, and watched on its own words.

    **This is the gate's remedy.** The review's table of refusals was counted
    by hand and was wrong, so the table is replaced by an enumeration that
    reads the product: a refusal added to ``labcairn.cli`` is found here
    whether or not anyone remembers to add a witness, and a witness removed is
    found here too.

    **A witness of its own is named, not merely counted.** The enumeration
    says which witness watches which refusal — the configuration's refusal is
    watched by the test that compares the configuration's path, and not by
    the test that compares the policy's — so that a refusal cannot be held
    watched by a witness that watches something else.
    """
    refusals = _refusals()
    groups = _groups(refusals)
    witnesses: list[Witness] = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    named, additional = _paired(refusals, witnesses, candidates, _recorded(refusals))
    suite = _tests_in_the_suite()

    unwatched = _unwatched_refusals(refusals, named, suite)
    assert not unwatched, (
        "these refusals have no witness of their own:\n"
        + "\n".join(
            f"  {refusal.place}  {refusal.words!r}\n"
            f"    the witness this enumeration names — {place or '(none)'} — "
            "is not in the suite"
            for refusal, place in unwatched
        )
        + "\n\nA witness quotes a phrase of the refusal's own words and names the "
        "value that refusal names. Add one that does."
    )

    watchers: dict[str, list[str]] = {}
    for index, place in named.items():
        watchers.setdefault(place, []).append(refusals[index].place)
    for index, places in additional.items():
        for place in places:
            watchers.setdefault(place, []).append(refusals[index].place)
    shared = {place: places for place, places in watchers.items() if len(places) > 1}
    assert not shared, (
        "one witness was given to two refusals; a witness watches one refusal:\n"
        + "\n".join(f"  {place}  {places}" for place, places in sorted(shared.items()))
    )


def test_the_gate_notices_a_refusal_nobody_watches_and_a_witness_that_is_gone() -> None:
    """The gate's teeth, checked by changing the tree on purpose.

    **A gate that stops biting is worse than a gate that is missing.** The
    enumeration is there for two failures — a refusal added to the CLI that
    nobody watches, and a witness taken out of the suite — and a gate that
    had stopped catching either would pass on a tree where the product had
    lost its watching.

    **Both are asked of the gate's own condition**, so what is checked is
    the condition the gate turns on and not a copy of it: a refusal whose
    sentence no test in the suite compares, and a suite without the witness
    of one refusal.
    """
    refusals = _refusals()
    groups = _groups(refusals)
    witnesses = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    recorded = _recorded(refusals)
    named, _additional = _paired(refusals, witnesses, candidates, recorded)
    suite = _tests_in_the_suite()

    assert not _unwatched_refusals(refusals, named, suite), (
        "the tree the gate runs on already has a refusal nobody watches, so "
        "the checks below would pass for the wrong reason"
    )

    stranger = Refusal(
        refusals[0].path,
        refusals[0].line,
        "raise",
        ("a sentence that no test in the suite compares",),
    )
    with_stranger = [*refusals, stranger]
    stranger_named, _ = _paired(
        with_stranger,
        witnesses,
        {**candidates, len(refusals): []},
        recorded,
    )
    unwatched = _unwatched_refusals(with_stranger, stranger_named, suite)
    assert [refusal.words for refusal, _ in unwatched] == [stranger.words], (
        "a refusal nobody watches was watched anyway, so a refusal added to "
        "the CLI without a witness would pass the gate"
    )

    watched = next(
        index for index in range(len(refusals)) if refusals[index].watches and index in named
    )
    without = {place: witness for place, witness in suite.items() if place != named[watched]}
    unwatched = _unwatched_refusals(refusals, named, without)
    assert [refusal.place for refusal, _ in unwatched] == [refusals[watched].place], (
        "a refusal whose witness was taken out of the suite was still "
        "watched, so a witness removed would pass the gate"
    )


def test_the_witnesses_that_are_recorded_are_in_the_suite() -> None:
    """Every recorded witness exists, and watches the refusal it is recorded for.

    **A record is only worth what it says.** The pairing that the value
    cannot decide is written down, and a witness that no longer names a test
    would leave the refusal unwatched without anything saying so.
    """
    refusals = _refusals()
    groups = _groups(refusals)
    witnesses: list[Witness] = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    recorded = _recorded(refusals)
    suite = _tests_in_the_suite()
    owned = _owned_phrases(refusals, groups)

    for index, (witness, others) in recorded.items():
        refusal = refusals[index]
        group = next(group for group, members in groups.items() if index in members)
        for place in (witness, *others):
            assert place in suite, (
                f"the record names {place!r} as a witness of {refusal.place}, and "
                "there is no such test in the suite."
            )
            assert any(
                phrase in text or text in phrase
                for phrase in owned[group]
                for text in suite[place].texts
                if len(_words(text)) >= MINIMUM_WORDS
            ), (
                f"{place} does not compare a phrase {refusal.place} says, so it "
                "does not watch that refusal."
            )

    offered = {
        witnesses[witness_index].place
        for index in recorded
        for witness_index in candidates.get(index, [])
    }
    named = {place for witness, others in recorded.values() for place in (witness, *others)}
    assert offered <= named, (
        "these witnesses could watch a recorded refusal and are not recorded "
        "for it:\n"
        + "\n".join(f"  {place}" for place in sorted(offered - named))
        + "\n\nEvery witness the derivation offers must be written down, or the "
        "record is not the whole of the pairing."
    )


def test_the_two_enumerations_watch_the_same_refusals_the_same_way() -> None:
    """The ledger and this enumeration name the same witness for the same site.

    **Two enumerations that can drift apart are one enumeration and a half.**
    The ledger names the witness of every site the CLI raises as a
    ``WorkspaceSetupError``; this one derives the witness of every refusal
    the CLI raises, by the value the refusal names. Where they overlap they
    must agree, or one of them is wrong about which witness watches which
    site — and the ledger's own check cannot tell the configuration's
    witness from the policy's, because both compare the same three words.
    """
    from test_cli_workspace_refusals import WATCHED_REFUSALS

    refusals = _refusals()
    groups = _groups(refusals)
    witnesses: list[Witness] = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    named, additional = _paired(refusals, witnesses, candidates, _recorded(refusals))

    by_name: dict[str, list[str]] = {}
    for witness in witnesses:
        by_name.setdefault(witness.function, []).append(witness.place)

    disagreements: list[str] = []
    for module, function, phrase, ledger_witnesses in WATCHED_REFUSALS:
        found = [
            index
            for index, refusal in enumerate(refusals)
            if refusal.path.relative_to(REPOSITORY_ROOT).as_posix() == module
            and refusal.function == function
            and phrase in refusal.words
        ]
        assert len(found) == 1, (
            f"the ledger names a refusal in {module}::{function} that the product "
            f"does not raise, or names more than one: {phrase!r}"
        )
        index = found[0]
        mine = {named.get(index, "")} | set(additional.get(index, ()))
        mine_names = {place.rsplit("::", 1)[-1] for place in mine}
        if len(mine_names) != len(mine):
            disagreements.append(
                f"  {module}::{function} {phrase!r}\n"
                "    this enumeration names two witnesses called the same thing, "
                f"and a name cannot say which is which: {sorted(mine)}"
            )
            continue
        ambiguous = [name for name in ledger_witnesses if len(by_name.get(name, ())) > 1]
        if ambiguous:
            disagreements.append(
                f"  {module}::{function} {phrase!r}\n"
                "    the ledger names witnesses that two tests in the suite call "
                f"the same thing: {ambiguous}"
            )
            continue
        if mine_names != set(ledger_witnesses):
            disagreements.append(
                f"  {module}::{function} {phrase!r}\n"
                f"    the ledger names      {sorted(ledger_witnesses)}\n"
                f"    this enumeration names {sorted(mine_names)}"
            )
    assert not disagreements, (
        "the ledger and this enumeration disagree about which witness watches "
        "which refusal:\n" + "\n".join(disagreements)
    )


def test_the_enumeration_agrees_with_the_text_of_the_cli_package() -> None:
    """The parser and a text scan must find the same refusals.

    **A parser that silently finds nothing would pass every other test in
    this file.** So the enumeration is checked against a scan of the same
    sources that does not parse anything: if the two disagree, the
    enumeration is wrong and this fails first.
    """
    refusals = _refusals()
    raised = [refusal for refusal in refusals if refusal.kind == "raise"]
    classes = _refusal_classes()
    assert classes, "the CLI defines no exception class of its own"

    scanned = 0
    for path in _modules(CLI_PACKAGE):
        text = path.read_text(encoding="utf-8")
        for name in classes:
            scanned += len(re.findall(rf"raise\s+{name}\b", text))
    assert scanned == len(raised), (
        f"the parser found {len(raised)} refusals and the text scan found {scanned}; "
        "the enumeration is not reading the product"
    )
    assert raised, "the enumeration found no refusal to watch"
    refused = len(re.findall(r"(?<!def )_refuse\(", _sources_text()))
    assert refused == len(refusals) - len(raised), (
        f"the parser found {len(refusals) - len(raised)} command refusals and the text "
        f"scan found {refused}; the enumeration is not reading the product"
    )


def test_every_refusal_the_cli_raises_says_words_of_its_own() -> None:
    """A refusal that says nothing of the CLI's own is not one to watch here.

    A message that is only ``str(error)`` carries no words of the CLI's: it
    is another component's refusal passing through, and a witness for it
    would be a witness of that component's words. This test says so for the
    refusals the CLI raises, so that the boundary of what is watched here is
    written down rather than assumed. The command's own refusals are the
    ones that carry another component's words, and the enumeration leaves
    them out for the same reason.
    """
    refusals = _refusals()
    silent = [refusal for refusal in refusals if refusal.kind == "raise" and not refusal.pieces]
    assert not silent, "these refusals raise no words of the CLI's own:\n" + "\n".join(
        f"  {refusal.place}" for refusal in silent
    )


def test_the_failures_that_cannot_happen_are_still_there() -> None:
    """The list of unreachable failures is not stale, and does not hide one.

    **A list of exceptions is a list like any other, and it can go stale.**
    Two things are checked: that each failure in the list is still handled
    somewhere in the CLI, so that the list is not naming something that has
    gone; and that no refusal excluded by it has a witness, so that a
    refusal that has become watchable is not left out of the enumeration
    because a list nobody looked at still said so.
    """
    refusals = _refusals()
    handled = {failure for refusal in refusals for failure in refusal.handled}
    stale = sorted(UNREACHABLE_FAILURES - handled)
    assert not stale, (
        "these failures are no longer handled anywhere in the CLI, so the list of "
        f"failures that cannot happen is stale: {stale}"
    )

    groups = _groups(refusals)
    witnesses: list[Witness] = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    for index, refusal in enumerate(refusals):
        if refusal.watches:
            continue
        if any(failure in UNREACHABLE_FAILURES for failure in refusal.handled):
            assert not candidates.get(index), (
                f"{refusal.place} is excluded because it handles a failure that cannot "
                "happen, but a witness quotes it now; it is watchable, so it belongs "
                "in the enumeration"
            )


def test_the_cli_refuses_in_more_than_one_way() -> None:
    """Both shapes of the CLI's refusal are read, and both are watched.

    The CLI raises ``WorkspaceSetupError`` for the refusals the workspace
    module owns, and it calls its own ``_refuse`` for the refusals a command
    owns. **Both are required to have a witness here**, because the words of
    the second are what tell the first apart from its neighbours: a witness
    of the policy's "could not be read as JSON" has to be told from the
    configuration's, and the command's own refusal of the same condition is
    a third.
    """
    refusals = _refusals()
    kinds = {refusal.kind for refusal in refusals}
    assert kinds == {"raise", "_refuse"}, kinds


def test_the_words_a_witness_quotes_are_the_products_own() -> None:
    """A witness quotes the product's words, and the product says them.

    **The messages here are the product's, not this file's.** The runs are
    read out of the CLI's own sources, so a refusal whose words change
    changes what a witness has to quote — and the enumeration above is what
    notices that a witness has stopped watching it.
    """
    refusals = _refusals()
    assert refusals, "the CLI raises no refusal at all"
    for refusal in refusals:
        assert refusal.pieces or refusal.kind == "_refuse", (
            f"{refusal.place} has no words; a witness cannot quote it"
        )


def test_the_granularity_is_the_test_and_not_the_file() -> None:
    """A file's import does not make every test in it a candidate.

    **The mechanism needs a witness of its own.** The gate reads the tests,
    so a rule that reads the tests is a mechanism, and a mechanism with no
    witness can be neutered while the whole tree stays green. This one
    holds the rule that decides *who* is a candidate: the rule reads the
    test, not the file the test lives in.

    The file used here is a real one whose tests divide: some of them reach
    the CLI and some do not. If the rule went back to reading the file, the
    division would disappear and this witness would go red.

    Red by: the candidate rule reading a module's imports instead of a
    test's own.
    """
    module = "test_cli_layer_models"
    tree = _tree_of(module)
    assert tree is not None, f"{module} is not readable"
    assert _imports_the_cli(tree), (
        f"{module} reaches the CLI at file level, which is this witness's premise"
    )
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(functions) > 1, f"{module} has too few tests to divide"
    reaching = [function for function in functions if _witness_reaches_the_cli(function, module)]
    assert reaching, f"no test in {module} reaches the CLI, which cannot be true"
    assert len(reaching) < len(functions), (
        f"every test in {module} is a candidate, so the rule is reading the file "
        f"rather than the test"
    )
    quiet = [function for function in functions if function not in reaching]
    assert quiet, f"no test in {module} stays away from the CLI"
    assert not any(_witness_reaches_the_cli(function, module) for function in quiet), (
        "a test that does not reach the CLI is a candidate anyway"
    )


# --------------------------------------------------------------------------- #
# the mechanism's own witnesses
#
# **The gate is a mechanism that reads the tree, and a mechanism needs a
# witness of its own.** Two rules decide what the gate watches: the rule
# that reads a refusal's message, and the rule that decides who is a
# candidate. Both were measured, both were broken, and each has a witness
# below that drives the gate over the tree's own sources and goes red when
# the rule is broken.
#
# **The witnesses drive the gate; they do not inspect it.** Each hands the
# mechanism a source — the product's own file with a message hoisted into
# a constant, the suite's own module with a test that reaches nothing — and
# then asks the gate what it makes of it. Nothing here asserts what a
# helper returns.
# --------------------------------------------------------------------------- #


#: The name a witness gives the constant it hoists a message into.
_HOISTED_NAME: Final[str] = "_A_MESSAGE_THE_WITNESS_HOISTED"


def _reader(overrides: dict[Path, str]) -> Callable[[Path], str]:
    """A reader that returns the text *overrides* names, and the files otherwise.

    **The gate is driven over sources, and this is how a witness drives it
    over a source of its own.** Every file the gate does not name is read
    as it is on disk.
    """

    def read(path: Path) -> str:
        return overrides.get(path, path.read_text(encoding="utf-8"))

    return read


def _forget(module: str) -> None:
    """Forget what was read about the test module *module*.

    **A witness that reads a module differently has to have it read again.**
    The mechanism reads each test module once, and the witness that hands
    it another source has to have that source read instead of the one on
    disk — otherwise the mechanism answers from the source it read first,
    and the witness proves nothing.
    """
    _TREES.pop(module, None)
    _BINDINGS.pop(module, None)
    for pair in [key for key in _USES if key[0] == module]:
        del _USES[pair]
    for pair in [key for key in _HOLDS if key[0] == module]:
        del _HOLDS[pair]
    for pair in [key for key in _IMPORTS if key[0] == module]:
        del _IMPORTS[pair]
    for pair in [key for key in _REACHES if key[0] == module]:
        del _REACHES[pair]
    for test in [key for key in _TEST_REACHES if key[0] == module]:
        del _TEST_REACHES[test]


def _line_starts(text: str) -> list[int]:
    """The byte offset each line of *text* begins at.

    **Bytes, because the parser counts bytes.** A column offset is counted
    from the start of its line in UTF-8 bytes, and a line's own bytes are
    what the offset is counted in.
    """
    starts: list[int] = []
    offset = 0
    for line in text.split("\n"):
        starts.append(offset)
        offset += len(line.encode("utf-8")) + 1
    return starts


def _message_node(tree: ast.Module, line: int, kind: str) -> ast.expr | None:
    """The message the refusal at *line* of *tree* writes.

    **The refusal is found by where it is.** A ``raise`` carries its
    message as the exception's first argument and a ``_refuse`` call as
    its second, and the two shapes are told apart by the kind.
    """
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) != line:
            continue
        if kind == "raise" and isinstance(node, ast.Raise):
            if isinstance(node.exc, ast.Call) and node.exc.args:
                return node.exc.args[0]
            return None
        if (
            kind == "_refuse"
            and isinstance(node, ast.Call)
            and _called_name(node) == "_refuse"
            and len(node.args) > 1
        ):
            return node.args[1]
    return None


def _anchor_line(tree: ast.Module, line: int) -> int:
    """The line of the top-level statement that holds *line*.

    **The constant goes at the module's top level**, before the statement
    that holds the refusal, so that it is a module's own binding and not a
    function's.
    """
    for node in tree.body:
        end = node.end_lineno or node.lineno
        if node.lineno <= line <= end:
            return node.lineno
    raise AssertionError(f"line {line} of the module is in no top-level statement")


def _hoisted_source(path: Path, line: int, kind: str, name: str) -> str:
    """The source at *path* with the refusal at *line* written as a constant.

    **The product's own file, with one message hoisted.** The message is
    taken out of the call that writes it and put at the module's top level
    under *name*, and the call is left naming it. The words are the same
    words — which is the point: **a message written as a constant says
    what it always said**, and the gate has to see that it does.
    """
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    message = _message_node(tree, line, kind)
    assert message is not None, f"{path}:{line} writes no message to hoist"
    starts = _line_starts(text)
    data = text.encode("utf-8")
    start = starts[message.lineno - 1] + message.col_offset
    end = starts[(message.end_lineno or message.lineno) - 1] + (message.end_col_offset or 0)
    body = data[start:end].decode("utf-8")
    anchor = starts[_anchor_line(tree, line) - 1]
    constant = f"{name} = (\n{body}\n)\n"
    replaced = data[:start] + name.encode("utf-8") + data[end:]
    inserted = replaced[:anchor] + constant.encode("utf-8") + replaced[anchor:]
    return inserted.decode("utf-8")


def _a_watched_literal_refusal(
    refusals: list[Refusal],
    candidates: dict[int, list[int]],
    named: dict[int, str],
) -> tuple[int, Refusal] | None:
    """The first refusal whose message is a literal and whose witness is its own.

    **One candidate and no other**, so that taking the witness away leaves
    the refusal with none — which is what the witnesses have to show. And a
    message that is a literal, so that hoisting it into a constant says the
    same words and the same values: a message that interpolates a value
    would read differently once it was hoisted, and the witness would be
    showing something else.
    """
    trees: dict[Path, ast.Module] = {}
    for index, refusal in enumerate(refusals):
        if refusal.kind != "_refuse" or not refusal.watches:
            continue
        if index not in named or len(candidates.get(index, [])) != 1:
            continue
        if refusal.path not in trees:
            trees[refusal.path] = _parse(refusal.path)
        node = _message_node(trees[refusal.path], refusal.line, refusal.kind)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return index, refusal
    return None


def _a_text_that_speaks_for(
    refusal: Refusal,
    refusals: list[Refusal],
    groups: dict[tuple[str, ...], list[int]],
    texts: tuple[str, ...],
) -> str:
    """The text of *texts* that speaks for *refusal* and for no other group.

    **The same words the refusal's own witness quotes, and long enough to
    be quoted at all.** A candidate quotes a *phrase*, and a text of one
    word names no group — so a text that names the refusal and is too
    short to be a phrase is not what the rule that admits a candidate
    looks at. And a test that quoted a text of another group as well
    would watch neither, and the witness would be showing a rule that was
    never broken.
    """
    owned = _owned_phrases(refusals, groups)
    for text in texts:
        if len(_words(text)) < MINIMUM_WORDS:
            continue
        spoken_for = {
            group
            for group, phrases in owned.items()
            if any(phrase in text or text in phrase for phrase in phrases)
        }
        if spoken_for == {refusal.pieces}:
            return text
    raise AssertionError(f"no text of {texts!r} speaks for {refusal.place}")


@pytest.fixture
def drive_over(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[dict[Path, str]], None]]:
    """Let a witness hand the mechanism the sources it wants read.

    **The mechanism reads each test module once**, so a witness that hands
    it another source has to have that source read instead of the one on
    disk — and the module has to be read again afterwards, or the source
    the witness wrote would be read by every test that follows.
    """
    driven: list[str] = []

    def drive(overrides: dict[Path, str]) -> None:
        monkeypatch.setattr(sys.modules[__name__], "_read", _reader(overrides))
        for path in overrides:
            driven.append(path.stem)
            _forget(path.stem)

    yield drive

    for module in driven:
        _forget(module)


def test_a_refusal_whose_message_the_product_hoisted_is_still_watched(
    drive_over: Callable[[dict[Path, str]], None],
) -> None:
    """A message the product wrote as a constant is still watched.

    **What would make this red.** The rule that reads a refusal's message
    resolves a literal, an interpolated string and a call to a function of
    the same module — and, if it is broken, not a *name*. A refusal whose
    message the product wrote as a module constant would then have no
    words of its own, would leave the watch set, and would be watched by
    nobody without anything saying so: **the gate would be green on a tree
    whose refusal had stopped being watched**, and the witness of that
    refusal could be taken away without anything turning red.

    **The tree's own refusal is the one that is hoisted, and the tree's
    own witness is the one that must keep watching it.** The source the
    gate reads is the product's own file with one message written as a
    constant, and the gate is driven over that source exactly as it is
    driven over the tree's.
    """
    refusals = _refusals()
    groups = _groups(refusals)
    witnesses = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    named, _additional = _paired(refusals, witnesses, candidates, _recorded(refusals))
    suite = _tests_in_the_suite()

    assert not _unwatched_refusals(refusals, named, suite), (
        "the tree the gate runs on already has a refusal nobody watches, so the "
        "checks below would pass for the wrong reason"
    )
    target = _a_watched_literal_refusal(refusals, candidates, named)
    assert target is not None, (
        "the tree holds no refusal written as a literal with a witness of its own, "
        "so this witness has no message to hoist"
    )
    index, refusal = target
    place = named[index]

    drive_over(
        {refusal.path: _hoisted_source(refusal.path, refusal.line, refusal.kind, _HOISTED_NAME)}
    )

    after = _refusals()
    after_groups = _groups(after)
    after_candidates = _candidates(witnesses, after, after_groups)
    after_named, _ = _paired(after, witnesses, after_candidates, _recorded(after))
    after_suite = _tests_in_the_suite()

    found = next(
        (
            other
            for other_index, other in enumerate(after)
            if other.path == refusal.path
            and other.function == refusal.function
            and other.words == refusal.words
        ),
        None,
    )
    assert found is not None, "the refusal is not in the enumeration once its message is hoisted"
    assert found.pieces == refusal.pieces, (
        "the message written as a constant does not read as the words it wrote before"
    )
    assert after_named.get(after.index(found)) == place, (
        "the refusal whose message the product wrote as a constant is not watched "
        "by the witness that watched it: the rule that reads a message does not "
        "read a name"
    )

    without = {where: witness for where, witness in after_suite.items() if where != place}
    unwatched = _unwatched_refusals(after, after_named, without)
    assert any(
        other.path == refusal.path
        and other.function == refusal.function
        and other.words == refusal.words
        for other, _ in unwatched
    ), (
        "the refusal was still watched after its witness was taken out of the "
        "suite, so a witness removed would pass the gate"
    )


def test_a_test_that_quotes_a_refusal_reason_and_reaches_nothing_is_not_a_candidate(
    drive_over: Callable[[dict[Path, str]], None],
) -> None:
    """A reason quoted by a test that reaches nothing is not a candidate.

    **What would make this red.** The rule that decides candidacy used to
    take a test as reaching the CLI when the test said one of the CLI's
    own refusal reasons. The reasons are vocabulary the CLI shares with
    the rest of the product, so a test that quoted one and reached nothing
    was made a candidate — and a refusal that interpolates no value cannot
    be narrowed to one candidate, so the gate went red on a tree whose
    product had not changed. The second reader measured it: a new test
    that named a reason and quoted a refusal's words took that refusal's
    witness away from it.

    **The tree's own refusal is the one that would be disturbed, and the
    tree's own witness is the one that must keep watching it.** The suite
    the gate reads is the tree's own module with one test added: a test
    that names a refusal reason and quotes the refusal's own words, and
    reaches nothing at all.
    """
    refusals = _refusals()
    groups = _groups(refusals)
    witnesses = _suite_witnesses()
    candidates = _candidates(witnesses, refusals, groups)
    named, _additional = _paired(refusals, witnesses, candidates, _recorded(refusals))

    target = _a_watched_literal_refusal(refusals, candidates, named)
    assert target is not None, (
        "the tree holds no refusal written as a literal with a witness of its own, "
        "so this witness has no refusal to disturb"
    )
    index, refusal = target
    place = named[index]
    witness = witnesses[candidates[index][0]]
    reasons = _cli_refusal_reasons()
    reason = next((text for text in witness.texts if text in reasons), min(reasons))
    quoted = _a_text_that_speaks_for(refusal, refusals, groups, witness.texts)

    module_path = REPOSITORY_ROOT / place.split("::")[0]
    module = module_path.stem
    added = "test_a_reason_quoted_where_nothing_is_reached"
    original = module_path.read_text(encoding="utf-8")
    assert f"def {added}(" not in original, f"{module_path} already holds a test of that name"
    addition = (
        "\n\n"
        f"def {added}() -> None:\n"
        '    """A refusal reason and a refusal\'s words, where no CLI is reached."""\n'
        f"    reason = {reason!r}\n"
        f"    assert reason == {reason!r}\n"
        f"    assert {quoted!r} == {quoted!r}\n"
    )
    drive_over({module_path: original + addition})

    after = _refusals()
    after_groups = _groups(after)
    after_witnesses = _suite_witnesses()
    after_candidates = _candidates(after_witnesses, after, after_groups)
    after_named, _ = _paired(after, after_witnesses, after_candidates, _recorded(after))
    after_suite = _tests_in_the_suite()

    assert after_named == named, (
        "a test that quotes a refusal reason and reaches nothing changed the "
        "pairing: the rule that admits a candidate admits it on a proxy that "
        "unrelated code can satisfy"
    )
    assert after_named.get(index) == place, (
        "the refusal the added test would have disturbed is not watched by a "
        "witness of its own any more"
    )
    assert place in after_suite, "the refusal's witness is not in the suite"

    added_place = f"{module_path.relative_to(REPOSITORY_ROOT).as_posix()}::{added}"
    assert all(candidate.place != added_place for candidate in after_witnesses), (
        "the test that reaches nothing was made a witness: the rule admits a "
        "candidate on a proxy that unrelated code can satisfy"
    )

    tree = _tree_of(module)
    assert tree is not None, f"{module} is not readable"
    function = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == added
    )
    assert _holds_a_reason(function, reasons), (
        "the added test does not say a refusal reason, so this witness's premise "
        "is not the case the second reader measured"
    )
    assert not _witness_reaches_the_cli(function, module), (
        "the added test reaches the CLI, so this witness's premise is not the "
        "case the second reader measured"
    )
