"""The words a witness compares, read out of the test that writes them.

**A refusal is watched by a test that compares the product's words with what
the product said.** Not by a test that *holds* them. The difference is the
whole of the property, and it was measured: a witness that keeps the refusal's
sentence as a string constant and stops comparing it (``_ = expected``) passes
every enumeration that asks only whether the phrase is *in* the witness's body,
and the whole test suite passes with it, because a test that compares nothing
about the refusal still passes about everything else.

So the rule this module states is narrow and exact:

* a witness's **text** is a constant the test writes — a literal, the literal
  parts of an interpolated one, or a name bound to such a literal;
* a witness's text is **compared** when the test puts it beside the product's
  output inside an assertion: as an operand of a comparison, or as an argument
  of a call.

:func:`compared_texts` returns the second kind and nothing else. A test that
merely holds a phrase returns no text for it, and an enumeration that asks for
one says so.

**The values a witness interpolates are left out.** What a witness quotes is
the product's *words*; the values the product puts in them are the product's
business and change with the workspace. A witness that says *"the source
directory 'materials' is missing"* with its own path in it is a witness of the
refusal's sentence, and the sentence is what this module reads.

**This module is the machinery, not a witness.** It says how a test's own words
are read; it says nothing about which refusal any of them watches. The two
enumerations that ask that question are
``tests/test_cli_workspace_refusals.py`` and
``tests/test_cli_refusal_enumeration.py``, and they share this reading so that
they cannot drift apart on what "a witness" means.
"""

from __future__ import annotations

import ast


def literal_text(node: ast.AST, bindings: dict[str, str]) -> str:
    """The words *node* writes, with the values it interpolates left out.

    A name is read through *bindings*, so a sentence the test builds once and
    asserts by name is read as the sentence it wrote.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_part_text(value, bindings) for value in node.values)
    if isinstance(node, ast.Name):
        return bindings.get(node.id, "")
    return ""


def _part_text(node: ast.AST, bindings: dict[str, str]) -> str:
    """The words one part of an interpolated string writes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.FormattedValue):
        return literal_text(node.value, bindings)
    return ""


def bindings_of(function: ast.FunctionDef) -> dict[str, str]:
    """The strings *function* binds to a name, by the time it asserts them.

    **A binding is not a comparison.** The map is here so that a sentence the
    test writes once and asserts by name can be read back; whether the test
    *compares* it is :func:`compared_texts`'s question and not this one's.
    """
    bindings: dict[str, str] = {}
    assignments = sorted(
        (
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Assign) and len(node.targets) == 1
        ),
        key=lambda node: node.lineno,
    )
    for assignment in assignments:
        target = assignment.targets[0]
        if not isinstance(target, ast.Name):
            continue
        text = literal_text(assignment.value, bindings)
        if text:
            bindings[target.id] = text
    return bindings


def compared_texts(function: ast.FunctionDef) -> list[str]:
    """The texts *function* compares, and not merely holds.

    **Only assertions count.** A string in a docstring says nothing about what
    is watched; a string in a statement that is not an assertion says nothing
    either. A string in an assertion says something only where the assertion
    puts it beside the product's output — as an operand of a comparison, or as
    an argument of a call.

    ``assert "the source directory 'materials' is missing" in payload["message"]``
    compares. ``expected = "the source directory 'materials' is missing"``
    followed by ``_ = expected`` holds it and compares nothing, and this
    function returns no text for it.
    """
    bindings = bindings_of(function)
    texts: list[str] = []
    for statement in ast.walk(function):
        if not isinstance(statement, ast.Assert):
            continue
        texts.extend(_compared(statement.test, bindings))
    return texts


def _compared(node: ast.AST, bindings: dict[str, str]) -> list[str]:
    """The texts one assertion compares or calls with."""
    if isinstance(node, ast.Compare):
        found: list[str] = []
        for operand in (node.left, *node.comparators):
            found.extend(_operand_texts(operand, bindings))
        return found
    if isinstance(node, ast.Call):
        found = []
        for argument in node.args:
            found.extend(_operand_texts(argument, bindings))
        for keyword in node.keywords:
            found.extend(_operand_texts(keyword.value, bindings))
        return found
    if isinstance(node, ast.BoolOp):
        found = []
        for value in node.values:
            found.extend(_compared(value, bindings))
        return found
    if isinstance(node, ast.UnaryOp):
        return _compared(node.operand, bindings)
    return []


def _operand_texts(node: ast.AST, bindings: dict[str, str]) -> list[str]:
    """The text one operand of a comparison writes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        text = literal_text(node, bindings)
        return [text] if text else []
    if isinstance(node, ast.Name):
        text = bindings.get(node.id, "")
        return [text] if text else []
    return []


__all__ = [
    "bindings_of",
    "compared_texts",
    "literal_text",
]
