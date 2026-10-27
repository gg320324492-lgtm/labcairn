"""The rule that reads a witness is watched by a test of its own.

**The mechanism that does the watching has to be watched too.** The rule in
:mod:`tests.refusal_witnesses` says what a witness is: a test that *compares*
the product's words, not a test that *holds* them. Both enumerations read it,
so a rule that could no longer tell a comparison from a holding would take
both of them down with it — and the whole suite with them, because those two
enumerations were the only place in the repository the rule was read at all.

That was measured, not assumed. Neutering the rule so that it read a
*mention* rather than a comparison left the whole suite green, twice: once
with the rule changed on its own, and once with a real witness changed as
well so that it stopped comparing. The rule was the hole, and nothing in the
tree could see it.

So the rule is read here, by a test of its own, and what is read is
*compared* rather than asserted: a witness that compares the product's words
and a witness that only holds them are read differently, and a witness that
stops comparing is not read as comparing.

**This file says nothing about any refusal.** It says how the rule reads a
witness, and that the two enumerations read this rule and not a copy of it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest
from refusal_witnesses import compared_texts

pytestmark = pytest.mark.negative

#: The repository's root, found from this file.
REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: The two enumerations that read the shared rule.
#:
#: They are the rule's only consumers in the whole repository, so they are
#: where the rule's reach ends and where a copy of it would begin.
THE_ENUMERATIONS: Final[tuple[str, ...]] = (
    "tests/test_cli_refusal_enumeration.py",
    "tests/test_cli_workspace_refusals.py",
)

#: The phrase the witnesses here talk about.
PHRASE: Final[str] = "the source directory 'materials' is missing"

#: A witness that compares the phrase with what the product said.
COMPARING_WITNESS: Final[str] = '''
def witness(payload):
    """A witness of the refusal."""
    assert "the source directory 'materials' is missing" in payload["message"]
'''

#: The same phrase, put in a name and held.
#:
#: The phrase is still there, in the witness's own body. What the witness no
#: longer does is put the phrase beside the product's words, so it compares
#: nothing about the refusal.
HOLDING_WITNESS: Final[str] = '''
def witness(payload):
    """A witness of the refusal."""
    expected = "the source directory 'materials' is missing"
    _ = expected
'''

#: The phrase, written once and compared by name.
BOUND_WITNESS: Final[str] = '''
def witness(payload):
    """A witness of the refusal."""
    expected = "the source directory 'materials' is missing"
    assert expected in payload["message"]
'''

#: The phrase, handed to a call inside an assertion.
CALLED_WITNESS: Final[str] = '''
def witness(payload):
    """A witness of the refusal."""
    assert says(payload, "the source directory 'materials' is missing")
'''

#: The phrase, in the prose the witness is described by.
#:
#: **The docstring is the phrase itself, word for word.** A docstring that
#: merely contained the phrase would not be read as the phrase — the rule
#: reads whole texts — and a rule that read docstrings would then pass this
#: witness unnoticed. Writing it out exactly is what makes the docstring a
#: witness of the rule's blindness rather than a near miss.
DOCUMENTED_WITNESS: Final[str] = '''
def witness(payload):
    """the source directory 'materials' is missing"""
    assert payload["message"]
'''

#: The phrase, with a value written into it.
INTERPOLATED_WITNESS: Final[str] = '''
def witness(payload, name):
    """A witness of the refusal."""
    assert f"the source directory '{name}' is missing" in payload["message"]
'''


def _witness(source: str) -> ast.FunctionDef:
    """The witness function written in *source*."""
    functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
    assert len(functions) == 1, "the source must write exactly one witness"
    return functions[0]


def _read(source: str) -> list[str]:
    """The texts the rule reads out of the witness written in *source*."""
    return compared_texts(_witness(source))


def _first_literal(node: ast.AST) -> str | None:
    """The first string constant written in *node*."""
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            return child.value
    return None


def _stopped_copy(function: ast.FunctionDef) -> ast.FunctionDef:
    """The witness with its comparison turned into a holding.

    Each assertion becomes an assignment that binds the phrase it compared
    and holds it — which is what a witness that stops comparing looks like,
    and what the rule has to read as *not* comparing.
    """
    module = ast.parse(ast.unparse(function))
    stopped = module.body[0]
    assert isinstance(stopped, ast.FunctionDef), "the source must write one witness"
    body: list[ast.stmt] = []
    for statement in stopped.body:
        phrase = _first_literal(statement.test) if isinstance(statement, ast.Assert) else None
        if phrase is None:
            body.append(statement)
            continue
        holding = ast.Assign(
            targets=[ast.Name(id="_held", ctx=ast.Store())],
            value=ast.Constant(value=phrase),
        )
        ast.copy_location(holding, statement)
        body.append(holding)
    stopped.body = body
    return stopped


def _imports_of(tree: ast.Module, name: str) -> list[str]:
    """The modules *name* is imported from in *tree*."""
    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if alias.name == name:
                modules.append(node.module or "")
    return modules


def _defined_in(tree: ast.Module, name: str) -> list[str]:
    """Where *name* is bound by *tree* itself, rather than imported."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                found.append(f"a {type(node).__name__} named {name}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    found.append(f"an assignment to {name}")
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            found.append(f"an annotated assignment to {name}")
    return found


def test_a_phrase_the_witness_compares_is_read() -> None:
    """A phrase the witness puts beside the product's words is read.

    **This is the rule's own first case.** The phrase is an operand of a
    comparison inside an assertion, so the rule reads it — and the words it
    reads are the words the product wrote.
    """
    assert PHRASE in _read(COMPARING_WITNESS)


def test_a_phrase_the_witness_only_holds_is_not_read() -> None:
    """A phrase the witness binds and holds is not read.

    **Holding is not comparing.** The refusal's sentence stays in the witness
    as a string constant, so a rule that asked only whether the phrase is
    *mentioned* would read it — and would let a witness that watches nothing
    stand for a witness forever. The rule asks what the witness does with the
    phrase, and holding it is not comparing it.
    """
    assert PHRASE not in _read(HOLDING_WITNESS)


def test_a_witness_that_compares_and_one_that_only_holds_are_read_differently() -> None:
    """The pair differs, and the difference is the whole of the rule.

    **The minimal pair, and the only one that matters.** Two witnesses that
    hold the same phrase must not be read the same way, and the phrase must
    be the thing that separates them: a rule that read a *mention* would
    read both of them, and the pair would collapse into one.
    """
    comparing = _read(COMPARING_WITNESS)
    holding = _read(HOLDING_WITNESS)
    assert set(comparing) - set(holding) == {PHRASE}, (
        "the phrase the witness compares does not separate the two witnesses: "
        f"{comparing!r} and {holding!r}. A rule that reads a mention would "
        "read them the same way."
    )


def test_a_phrase_the_witness_binds_and_then_compares_by_name_is_read() -> None:
    """A phrase the test writes once and compares by name is read.

    **A name is not a comparison, but a name used in one is.** The rule reads
    the phrase through the binding the test gave it, so that a witness which
    states its expectation once and asserts it by name is not lost.
    """
    assert PHRASE in _read(BOUND_WITNESS)


def test_a_phrase_the_witness_calls_with_is_read() -> None:
    """A phrase the witness hands to a call inside an assertion is read.

    **A comparison is a comparison, whatever shape it is written in.** The
    phrase is an argument of a call the assertion makes, and the rule reads
    the arguments of a call as well as the operands of a comparison.
    """
    assert PHRASE in _read(CALLED_WITNESS)


def test_a_phrase_in_a_docstring_is_not_read() -> None:
    """A phrase in the prose a witness is described by is not read.

    **Prose about the refusal is not the refusal.** The docstring says what
    the test is for; it does not put the phrase beside the product's output,
    so it is not a witness of anything.
    """
    assert PHRASE not in _read(DOCUMENTED_WITNESS)


def test_an_interpolated_phrase_is_read_by_its_literal_parts() -> None:
    """A phrase the witness interpolates is read by the words around the value.

    **The values are the product's business.** What a witness quotes is the
    product's *words*; the value written into them changes with the
    workspace. So the phrase is read as the literal text around the
    interpolation and not as the whole of the sentence.
    """
    assert _read(INTERPOLATED_WITNESS) == ["the source directory '' is missing"]


def test_a_witness_that_stops_comparing_is_not_read_as_comparing() -> None:
    """The same witness, with its comparison gone, is read differently.

    **This is the property the whole gate leans on.** A witness that stops
    comparing watches nothing, and the rule has to say so: the two witnesses
    differ in one statement only, and the rule must read them apart. If it
    cannot, then a rule that reads a *mention* would be indistinguishable
    from this one, and every witness in the suite would be a witness of
    nothing.
    """
    comparing = _witness(COMPARING_WITNESS)
    stopped = _stopped_copy(comparing)
    assert compared_texts(comparing) == [PHRASE], (
        "the rule does not read the phrase the witness compares"
    )
    assert compared_texts(stopped) == [], (
        "the rule reads a witness that has stopped comparing as one that "
        f"compares: {compared_texts(stopped)}. Holding the refusal's phrase "
        "is not comparing it."
    )


def test_both_enumerations_read_the_shared_rule_and_not_a_copy_of_it() -> None:
    """The record's sentence, made into a test that can fail.

    *"Both enumerations use it, so they cannot drift apart."* The sentence
    is only true if both read **this** module's function and not a copy of
    it, so each file is read: it must import ``compared_texts`` from
    ``refusal_witnesses``, and it must not bind that name itself.
    """
    for relative in THE_ENUMERATIONS:
        path = REPOSITORY_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        imports = _imports_of(tree, "compared_texts")
        assert imports == ["refusal_witnesses"], (
            f"{relative} does not read compared_texts from refusal_witnesses "
            f"(it reads it from {imports}). Both enumerations must read the "
            "one rule, or they can drift apart on what a witness is."
        )

        own = _defined_in(tree, "compared_texts")
        assert not own, (
            f"{relative} binds compared_texts itself ({own}). Two rules can "
            "drift apart; one rule cannot."
        )
