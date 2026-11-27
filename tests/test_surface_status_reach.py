"""The unreachable-state witness: no surface can move a record to ``verified_by_rule``.

**What this file watches.** The measurement of 2026-11-28
(``docs/acceptance/LC-P4-PILOT-verified-by-rule-unreachable-2026-11-28.md``)
found that :func:`labcairn.evidence.store.advance` -- the store's only writer
of the ``verified_by_rule`` status -- has **no caller anywhere in the
product**: every surface a person can reach writes ``planned``, ``extracted``
or ``user_attested``, and half of the evidence machinery around the status
(the second half of ``CITABLE_STATUSES``, the gate's C2/C3 re-verification,
the middle member of ``FINDING_STATUSES``) describes a state the product
cannot reach. This file is the witness that keeps that fact from disappearing
silently.

**What makes it red, and what a red means.** Wiring a verify surface means
importing or calling ``advance`` somewhere under ``src/labcairn/`` (the first
test), or naming ``VerificationStatus.VERIFIED_BY_RULE`` from one of the
surface packages -- ``application``, ``cli``, ``api`` -- that carry a
person's acts into the ledger (the second). Either edit turns this file red
**on the commit that closes the gap**. That red is the witness working, not a
regression: it says the record's central fact has stopped being true, and the
record names the options and their costs for exactly that moment. A red here
is a prompt to read (or update) the record, never a reason to revert a
deliberate decision.

**Why a source scan and not a behavioural test.** The property is
universal -- *no* code path writes the status -- so its behavioural form
would have to drive every surface that exists or ever will exist, and a new
surface would escape it silently. The honest mechanical form is the view the
interpreter itself loads: imports and calls as the ``ast`` module sees them,
not a regex over text, so a docstring that mentions ``advance``, a comment,
or the name inside another identifier does not match. The store's own
refusals (the model validator, ``_require_catalog_backed``, the transition
table) stay the second line behind this witness; dynamic indirection
(``getattr``, a stringly-typed dispatch) is the one spelling this scan
cannot see, and the record says so.

**Why ``tests/`` is not scanned.** The suite legitimately constructs the
state through ``advance`` -- thirty-one call sites across six files at the
measured commit -- because the machinery's own witnesses (the gate, the
report checks, the store's transition refusals) need a record in the state
to keep it honest. Scanning tests would go red on the very tests that hold
the machinery up.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

#: The product source this witness reads as data. ``src/`` only: the tests
#: exercise the writer on purpose (see the module docstring).
SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "labcairn"

#: The packages whose modules carry a person's or a service's acts into the
#: ledger. A status named here is a status a surface intends to write; the
#: vocabulary itself lives in ``labcairn.evidence.states`` and is described by
#: ``labcairn.evidence`` and ``labcairn.reports``, none of which a surface
#: needs in order to accept, attest or propose.
SURFACE_PACKAGES: tuple[str, ...] = ("application", "cli", "api")

_STORE_MODULE = "labcairn.evidence.store"
_STORE_PACKAGE = "labcairn.evidence"
_STATUS_MEMBER = "VERIFIED_BY_RULE"


def _iter_source_files() -> Iterator[Path]:
    yield from sorted(SRC_ROOT.rglob("*.py"))


def _package_files(package: str) -> Iterator[Path]:
    yield from sorted((SRC_ROOT / package).rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _attribute_chain(node: ast.expr) -> tuple[str, list[str]] | None:
    """The dotted chain behind an attribute access, as ``(root, attrs)``.

    ``labcairn.evidence.store.advance`` reads as root ``labcairn`` with attrs
    ``["evidence", "store", "advance"]``; ``store.advance`` as root ``store``
    with attrs ``["advance"]``. ``None`` when the chain does not end in a
    plain name (a subscript or call in the middle of it).
    """
    attrs: list[str] = []
    while isinstance(node, ast.Attribute):
        attrs.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return node.id, list(reversed(attrs))
    return None


def test_no_module_under_src_wires_the_advance_writer() -> None:
    """No product module imports or calls ``store.advance``.

    The scan reads every module under ``src/labcairn/`` -- the store module
    included, whose ``__all__`` entry and definition are prose to this scan --
    and refuses three shapes: a ``from labcairn.evidence.store import
    advance`` under any binding, a call to a bare ``advance`` name, and a call
    through a binding of the store module (``store.advance(...)`` and
    ``labcairn.evidence.store.advance(...)`` alike). Any one of them is a
    surface starting to wire the only writer of ``verified_by_rule``, and the
    record the module docstring names is what a red asks to be read.
    """
    offenders: list[str] = []
    for path in _iter_source_files():
        tree = _tree(path)
        advance_bindings: set[str] = set()
        store_alias_bindings: set[str] = set()
        store_root_bindings: set[str] = set()
        # Every binding in the module, at any nesting depth: a function-level
        # ``from labcairn.evidence.store import advance`` wires the writer as
        # surely as a top-level one, and a scan of ``tree.body`` alone would
        # let it through.
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    bound = alias.asname or alias.name
                    if module == _STORE_MODULE and alias.name == "advance":
                        advance_bindings.add(bound)
                        offenders.append(f"{path}: imports 'advance' from {_STORE_MODULE}")
                    elif module == _STORE_PACKAGE and alias.name == "store" and bound == "store":
                        store_alias_bindings.add(bound)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _STORE_MODULE:
                        if alias.asname is not None:
                            store_alias_bindings.add(alias.asname)
                        else:
                            store_root_bindings.add("labcairn")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in advance_bindings:
                offenders.append(f"{path}: calls 'advance' at line {node.lineno}")
                continue
            if isinstance(node.func, ast.Attribute):
                chain = _attribute_chain(node.func)
                if chain is None:
                    continue
                root, attrs = chain
                calls_advance = (root in store_alias_bindings and attrs == ["advance"]) or (
                    root in store_root_bindings and attrs == ["evidence", "store", "advance"]
                )
                if calls_advance:
                    offenders.append(f"{path}: calls the store's 'advance' at line {node.lineno}")
    assert offenders == [], (
        "a module under src/labcairn wires the only writer of "
        "'verified_by_rule' -- see the record this witness watches: " + "; ".join(offenders)
    )


def test_surface_packages_do_not_name_the_unreachable_status() -> None:
    """No surface package names ``VerificationStatus.VERIFIED_BY_RULE``.

    The three surface packages are where a person's act enters the product,
    and none of their code needs the unreachable status to accept, attest or
    propose: their vocabulary is ``planned``, ``extracted`` and
    ``user_attested``. Naming the member from a surface is the act of a
    surface about to write it -- which is exactly the gap closing, and the
    moment the record asks to be read. The evidence and reports packages are
    not scanned: describing the status is their job, and the scan would go
    red on the machinery that keeps the state machine honest.
    """
    offenders: list[str] = []
    for package in SURFACE_PACKAGES:
        for path in _package_files(package):
            for node in ast.walk(_tree(path)):
                if isinstance(node, ast.Attribute) and node.attr == _STATUS_MEMBER:
                    offenders.append(f"{path}: names '{_STATUS_MEMBER}' at line {node.lineno}")
                elif isinstance(node, ast.ImportFrom) and any(
                    alias.name == _STATUS_MEMBER for alias in node.names
                ):
                    offenders.append(f"{path}: imports '{_STATUS_MEMBER}' at line {node.lineno}")
    assert offenders == [], (
        "a surface package names the status no surface can write -- see the "
        "record this witness watches: " + "; ".join(offenders)
    )
