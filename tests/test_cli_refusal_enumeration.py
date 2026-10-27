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
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from refusal_witnesses import compared_texts
import pytest

pytestmark = pytest.mark.negative

#: The repository's root, found from this file.
REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: The CLI's own package — the surface whose refusals are enumerated here.
CLI_PACKAGE: Final[Path] = REPOSITORY_ROOT / "src" / "labcairn" / "cli"

#: Where the CLI declares its refusal reasons.
CLI_MODELS: Final[Path] = CLI_PACKAGE / "models.py"

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


def _parse(path: Path) -> ast.Module:
    """The syntax tree of the file at *path*."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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


def _value_text(node: ast.expr, bindings: dict[str, ast.expr]) -> str:
    """The source text of the value *node* names."""
    if isinstance(node, ast.Name) and node.id in bindings:
        return _source_text(bindings[node.id])
    return _source_text(node)


def _pieces(
    expression: ast.expr | None,
    functions: dict[str, ast.FunctionDef],
    seen: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """The literal runs a message is made of, with the values left out.

    A message is read as a **template**: the literal text the product
    writes, with each interpolated value left out. A witness quotes the
    literal text and may fill the values in — the policy file's refusal says
    *which* file could not be read, and the witness says the same three
    words with its own path in them — so a witness is a fragment of the
    template rather than of one rendering of it.

    A message that is built by a function of the same module is resolved by
    reading that function's return — the refusal's words are the words the
    helper writes, and the helper is in the same file.
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
        function = functions.get(name)
        if function is not None and name not in seen:
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    return _pieces(node.value, functions, seen | {name})
    return ()


def _values(
    expression: ast.expr | None,
    functions: dict[str, ast.FunctionDef],
    bindings: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """The values a message interpolates, as the product writes them.

    **The values are what tell two refusals that say the same words apart.**
    The configuration that cannot be read and the policy that cannot be read
    say the same three words; what separates them is the path each of them
    names, and a witness that compares the configuration's path is the
    witness of the configuration's refusal and not of the policy's.
    """
    if expression is None:
        return ()
    if isinstance(expression, ast.JoinedStr):
        return tuple(
            _value_text(value.value, bindings)
            for value in expression.values
            if isinstance(value, ast.FormattedValue)
        )
    if isinstance(expression, ast.Call):
        name = _called_name(expression)
        function = functions.get(name)
        if function is not None and name not in seen:
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    return _values(node.value, functions, _bindings(function), seen | {name})
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
        handled = _handler_failures(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                name = _called_name(node.exc)
                if name in classes:
                    message = node.exc.args[0] if node.exc.args else None
                    found.append(
                        Refusal(
                            path,
                            node.lineno,
                            "raise",
                            _pieces(message, functions),
                            _enclosing_function(every_function, node.lineno),
                            (),
                            _values(message, functions, _bindings_of(every_function, node.lineno)),
                        )
                    )
            elif isinstance(node, ast.Call) and _called_name(node) == "_refuse":
                message = node.args[1] if len(node.args) > 1 else None
                found.append(
                    Refusal(
                        path,
                        node.lineno,
                        "_refuse",
                        _pieces(message, functions),
                        _enclosing_function(every_function, node.lineno),
                        handled.get(id(node), ()),
                        _values(message, functions, _bindings_of(every_function, node.lineno)),
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


def _imports_the_cli(tree: ast.Module) -> bool:
    """Whether the module imports the CLI at all."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.startswith("labcairn.cli"):
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name.startswith("labcairn.cli") for alias in node.names
        ):
            return True
    return False


def _asserts_a_reason(tree: ast.Module, reasons: set[str]) -> bool:
    """Whether the module says one of the CLI's refusal reasons anywhere."""
    return any(isinstance(node, ast.Constant) and node.value in reasons for node in ast.walk(tree))


def _witness_modules() -> list[Path]:
    """The test modules that watch the CLI's refusals.

    **A module watches the CLI's refusals if it imports the CLI, or if it
    says one of the CLI's own refusal reasons.** Both are read from the
    product: the reasons are the CLI's, declared in
    :mod:`labcairn.cli.models`. A module that neither imports the CLI nor
    names its reasons is about something else, and the strings it asserts
    are not witnesses of anything the CLI refuses.
    """
    reasons = _cli_refusal_reasons()
    modules: list[Path] = []
    for path in sorted(TESTS_DIRECTORY.rglob("test_*.py")):
        if path.resolve() == Path(__file__).resolve():
            # This file does not witness itself. Its own strings are the
            # machinery's, not a product's.
            continue
        tree = _parse(path)
        if _imports_the_cli(tree) or _asserts_a_reason(tree, reasons):
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
    """
    witnesses: list[Witness] = []
    for function in [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)]:
        texts = tuple(compared_texts(function))
        if not texts:
            continue
        witnesses.append(Witness(path, function.name, texts, _witness_values(function)))
    return witnesses


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
            named[index] = witnesses[pool[0]].function
            continue
        narrowed = _narrowed(pool, refusal, witnesses)
        if len(narrowed) == 1:
            named[index] = witnesses[narrowed[0]].function
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
#: **The first name is the witness this enumeration names for the refusal,
#: and the rest are the other tests that watch it.** A refusal with two
#: watchers is still watched twice over: the named one is the witness the
#: enumeration says watches it, and the others are watched by it too — the
#: doctor names the module's refusal of a source root outside the workspace
#: because it says the same words, and the command's own test names the
#: command's refusal of the same condition for the same reason.
#:
#: **The record is checked, not trusted.** Every name in it must exist in
#: the suite and must compare a phrase its refusal says, and every witness
#: the derivation offers for those refusals must be named here — so a
#: witness that is added and left out of the record, or one that is removed
#: from the suite, is noticed here.
WATCHED_BY: Final[tuple[tuple[str, str, str, str, tuple[str, ...]], ...]] = (
    (
        "src/labcairn/cli/commands.py",
        "_resolve_source_dirs",
        "outside the workspace",
        "test_a_source_directory_the_command_names_outside_the_workspace_is_refused",
        ("test_a_source_dir_outside_the_workspace_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "_rule_from_mapping",
        'needs an "effect" of allow, ask or deny',
        "test_a_policy_rule_with_no_effect_is_refused",
        ("test_a_policy_rule_with_an_unknown_effect_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "outside the workspace",
        "test_a_source_directory_outside_the_workspace_is_refused",
        ("test_doctor_names_a_source_root_outside_the_workspace",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "which is not a directory",
        "test_a_source_directory_that_is_not_a_directory_is_refused",
        ("test_a_configured_source_directory_that_is_not_a_directory_is_refused",),
    ),
)


def _recorded(refusals: list[Refusal]) -> dict[int, tuple[str, tuple[str, ...]]]:
    """The recorded witness of each refusal, and the others that watch it.

    A refusal is named by **the module it is in**, **the function it is in**
    and **a phrase of the sentence it writes** — the three together name one
    site, because two sites in one function can share a prefix.
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


def _tests_in_the_suite() -> dict[str, Witness]:
    """Every witness the suite holds, by the test's name."""
    witnesses: dict[str, Witness] = {}
    for path in _witness_modules():
        for witness in _witnesses(_parse(path), path):
            witnesses[witness.function] = witness
    return witnesses


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
    witnesses: list[Witness] = [
        witness for path in _witness_modules() for witness in _witnesses(_parse(path), path)
    ]
    candidates = _candidates(witnesses, refusals, groups)
    named, additional = _paired(refusals, witnesses, candidates, _recorded(refusals))
    suite = _tests_in_the_suite()

    unwatched = [
        (refusals[index], named.get(index, ""))
        for index in range(len(refusals))
        if refusals[index].watches and (index not in named or named[index] not in suite)
    ]
    assert not unwatched, (
        "these refusals have no witness of their own:\n"
        + "\n".join(
            f"  {refusal.place}  {refusal.words!r}\n"
            f"    the witness this enumeration names — {name or '(none)'} — "
            "is not in the suite"
            for refusal, name in unwatched
        )
        + "\n\nA witness quotes a phrase of the refusal's own words and names the "
        "value that refusal names. Add one that does."
    )

    watchers: dict[str, list[str]] = {}
    for index, name in named.items():
        watchers.setdefault(name, []).append(refusals[index].place)
    for index, names in additional.items():
        for name in names:
            watchers.setdefault(name, []).append(refusals[index].place)
    shared = {name: places for name, places in watchers.items() if len(places) > 1}
    assert not shared, (
        "one witness was given to two refusals; a witness watches one refusal:\n"
        + "\n".join(f"  {name}  {places}" for name, places in sorted(shared.items()))
    )


def test_the_witnesses_that_are_recorded_are_in_the_suite() -> None:
    """Every recorded witness exists, and watches the refusal it is recorded for.

    **A record is only worth what it says.** The pairing that the value
    cannot decide is written down, and a name that no longer names a test
    would leave the refusal unwatched without anything saying so.
    """
    refusals = _refusals()
    groups = _groups(refusals)
    witnesses: list[Witness] = [
        witness for path in _witness_modules() for witness in _witnesses(_parse(path), path)
    ]
    candidates = _candidates(witnesses, refusals, groups)
    recorded = _recorded(refusals)
    suite = _tests_in_the_suite()
    owned = _owned_phrases(refusals, groups)

    for index, (witness, others) in recorded.items():
        refusal = refusals[index]
        group = next(group for group, members in groups.items() if index in members)
        for name in (witness, *others):
            assert name in suite, (
                f"the record names {name!r} as a witness of {refusal.place}, and "
                "there is no such test in the suite."
            )
            assert any(
                phrase in text or text in phrase
                for phrase in owned[group]
                for text in suite[name].texts
                if len(_words(text)) >= MINIMUM_WORDS
            ), (
                f"{name} does not compare a phrase {refusal.place} says, so it "
                "does not watch that refusal."
            )

    offered = {
        witnesses[witness_index].function
        for index in recorded
        for witness_index in candidates.get(index, [])
    }
    named = {name for witness, others in recorded.values() for name in (witness, *others)}
    assert offered <= named, (
        "these witnesses could watch a recorded refusal and are not recorded "
        "for it:\n"
        + "\n".join(f"  {name}" for name in sorted(offered - named))
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
    witnesses: list[Witness] = [
        witness for path in _witness_modules() for witness in _witnesses(_parse(path), path)
    ]
    candidates = _candidates(witnesses, refusals, groups)
    named, additional = _paired(refusals, witnesses, candidates, _recorded(refusals))

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
        if mine != set(ledger_witnesses):
            disagreements.append(
                f"  {module}::{function} {phrase!r}\n"
                f"    the ledger names      {sorted(ledger_witnesses)}\n"
                f"    this enumeration names {sorted(mine)}"
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
    witnesses: list[Witness] = [
        witness for path in _witness_modules() for witness in _witnesses(_parse(path), path)
    ]
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
