"""The rule-backed status's reach: the verify door is wired, and it is the only way in.

**What this file watched, and what it watches now.** The measurement of
2026-11-28
(``docs/acceptance/LC-P4-PILOT-verified-by-rule-unreachable-2026-11-28.md``)
found that :func:`labcairn.evidence.store.advance` -- the store's only writer
of the ``verified_by_rule`` status -- had **no caller anywhere in the
product**: every surface a person could reach wrote ``planned``, ``extracted``
or ``user_attested``, and half of the evidence machinery around the status
(the second half of ``CITABLE_STATUSES``, the gate's C2/C3 re-verification,
the middle member of ``FINDING_STATUSES``) described a state the product could
not reach. The file that used to be here asserted that absence, and it was
**red on the commit that closed the gap**. The owner chose the record's option
A: a verify surface calling ``advance``. The gap is closed, so the absence is
no longer true and the file is **inverted**: it now watches that the door
stays wired, that it is the one caller of the writer, and that the surfaces
still reach the status through the layer's operation rather than by calling
the writer themselves. The record's own section on this witness says the
same thing; if the two disagree, the witness wins and the record is corrected.

**What makes it red, and what a red means.** Now a red means a regression:
the application operation stopped calling ``advance`` with
``VERIFIED_BY_RULE`` (the first test), a surface package started calling the
store's writer directly or stopped importing the operation (the second), or
something other than the store began writing the status column with SQL (the
third). The state would silently become unreachable again, or writable from a
door that skipped the layer's checks.

**Why a source scan and not a behavioural test.** The property is structural
-- *which* module calls the writer -- so its behavioural form would have to
drive every surface and every module that exists or ever will exist. The
honest mechanical form is the view the interpreter itself loads: imports and
calls as the ``ast`` module sees them, not a regex over text, so a docstring
that mentions ``advance``, a comment, or the name inside another identifier
does not count.

The behavioural witnesses -- that a pass moves the record, that a refusal
does not, and that the report's gate cites the result -- live in
``tests/test_evidence_verify_door.py``, because a scan can say a call exists
and only a run can say what it does.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

#: The product source this scan reads as data. ``src/`` only: the tests
#: exercise the writer on purpose (see the module docstring).
SRC_ROOT: Final = Path(__file__).resolve().parent.parent / "src" / "labcairn"

#: The packages whose modules carry a person's or a service's acts into the
#: ledger. They may name the status only through the application operation;
#: the store's writer is not theirs to call.
SURFACE_PACKAGES: Final[tuple[str, ...]] = ("application", "cli", "api")

_STORE_MODULE: Final = "labcairn.evidence.store"
_STORE_PACKAGE: Final = "labcairn.evidence"
_STATUS_MEMBER: Final = "VERIFIED_BY_RULE"

#: The layer's operation, and the one module that calls the store's writer.
_OPERATION_MODULE: Final = "labcairn.application"
_OPERATION: Final = "verify_claim"
_OPERATION_FILE: Final = SRC_ROOT / "application" / "evidence.py"

#: The column the status lives in. The store owns every write of it; a second
#: module holding this SQL would be a door around ``advance`` and its rules.
_STATUS_WRITE: Final = "UPDATE evidence_records SET status"


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


def _advance_calls(path: Path) -> list[int]:
    """The line numbers at which *path* calls the store's ``advance``.

    Three shapes are recognised -- a bare ``advance(...)`` through a
    ``from labcairn.evidence.store import advance`` binding (at any nesting
    depth), ``store.advance(...)`` through a module binding, and the full
    ``labcairn.evidence.store.advance(...)`` chain -- because any of them is
    the same act.
    """
    tree = _tree(path)
    advance_bindings: set[str] = set()
    store_alias_bindings: set[str] = set()
    store_root_bindings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                bound = alias.asname or alias.name
                if module == _STORE_MODULE and alias.name == "advance":
                    advance_bindings.add(bound)
                elif module == _STORE_PACKAGE and alias.name == "store" and bound == "store":
                    store_alias_bindings.add(bound)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _STORE_MODULE:
                    if alias.asname is not None:
                        store_alias_bindings.add(alias.asname)
                    else:
                        store_root_bindings.add("labcairn")
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in advance_bindings:
            lines.append(node.lineno)
            continue
        if isinstance(node.func, ast.Attribute):
            chain = _attribute_chain(node.func)
            if chain is None:
                continue
            root, attrs = chain
            if (root in store_alias_bindings and attrs == ["advance"]) or (
                root in store_root_bindings and attrs == ["evidence", "store", "advance"]
            ):
                lines.append(node.lineno)
    return sorted(lines)


def _imports_operation(path: Path) -> bool:
    """Does *path* bind the layer's ``verify_claim`` from the layer's package?"""
    for node in ast.walk(_tree(path)):
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "") == _OPERATION_MODULE
            and any(alias.name == _OPERATION for alias in node.names)
        ):
            return True
    return False


def test_the_verify_operation_is_the_one_caller_of_the_advance_writer() -> None:
    """``application/evidence.py`` calls ``store.advance``; nothing else does.

    This is the inverted half of the record's witness. Before the gap closed,
    *no* module called the writer; now exactly one does, and it is the
    application layer's ``verify_claim``. The assertion is two-sided on
    purpose: a tree with no caller is the record's state back again (the
    status unreachable), and a tree with a second caller is a surface that
    skipped the layer's operation -- which is the act the record's option A
    says belongs in the layer.
    """
    callers = {path: lines for path in _iter_source_files() if (lines := _advance_calls(path))}
    assert set(callers) == {_OPERATION_FILE}, (
        "the store's only writer of 'verified_by_rule' must be called by the "
        f"layer's verify operation and no other module; callers found: "
        f"{ {str(path): lines for path, lines in callers.items()} }"
    )
    assert callers[_OPERATION_FILE], (
        "the verify operation no longer calls the store's 'advance'; the "
        "'verified_by_rule' status would be unreachable again -- see the record: "
        "docs/acceptance/LC-P4-PILOT-verified-by-rule-unreachable-2026-11-28.md"
    )


def test_the_operation_asks_the_store_for_the_rule_backed_status() -> None:
    """The call passes ``VerificationStatus.VERIFIED_BY_RULE`` as its target.

    A call to ``advance`` that asked for another status would leave the
    writer wired and the record's status still unreachable. The target is the
    call's third positional argument -- ``connection``, ``evidence_id``,
    ``to_status`` -- and it must be the member the vocabulary names.
    """
    targets: list[tuple[str, list[str]] | None] = []
    for node in ast.walk(_tree(_OPERATION_FILE)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "advance" and len(node.args) >= 3:
            targets.append(_attribute_chain(node.args[2]))
    assert ("VerificationStatus", [_STATUS_MEMBER]) in targets, (
        f"the verify operation's call to advance does not ask for {_STATUS_MEMBER}: {targets}"
    )


def test_the_surfaces_reach_the_status_through_the_operation() -> None:
    """CLI and API import the layer's operation and never call the writer.

    The surface packages may *name* the status -- the CLI prints it, the API's
    response model carries it -- but naming it is not writing it: the write is
    the operation's. What is watched here is that the two surfaces a person
    reaches import ``verify_claim`` from the layer, and that no module under
    ``cli/`` or ``api/`` calls ``store.advance`` or writes the status column
    itself.
    """
    for package in ("cli", "api"):
        importers = [path for path in _package_files(package) if _imports_operation(path)]
        assert importers, (
            f"no module under {package}/ imports the layer's {_OPERATION!r}; "
            "the surface no longer reaches the rule-backed status"
        )
    offenders: list[str] = []
    for package in SURFACE_PACKAGES:
        for path in _package_files(package):
            if path == _OPERATION_FILE:
                continue
            if _advance_calls(path):
                offenders.append(f"{path}: calls the store's 'advance'")
            if _names_the_status_member(path):
                offenders.append(f"{path}: names {_STATUS_MEMBER} outside the operation")
    assert offenders == [], (
        "a surface module writes or names the rule-backed status outside the "
        "layer's verify operation: " + "; ".join(offenders)
    )


def test_the_status_column_is_written_only_by_the_store() -> None:
    """No module outside ``evidence/store.py`` holds the status column's SQL.

    The store's ``advance`` and ``attest`` are the ledger's writers, and the
    only other way to move a record's status is a SQL client this scan cannot
    see. Inside the product, a second module holding this statement would be a
    door around Contract 2, the rule catalog and the identifier rule -- the
    three reasons the store is the boundary. ``store.py`` may hold it: that is
    the boundary doing its job.
    """
    holders: list[str] = []
    store_module = SRC_ROOT / "evidence" / "store.py"
    for path in _iter_source_files():
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _STATUS_WRITE in node.value
                and path != store_module
            ):
                holders.append(f"{path}:{node.lineno}")
    assert holders == [], (
        "the status column is written by SQL outside evidence/store.py: " + "; ".join(holders)
    )


def _names_the_status_member(path: Path) -> bool:
    """Does *path* reference the ``VERIFIED_BY_RULE`` member as a name chain?"""
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Attribute) and node.attr == _STATUS_MEMBER:
            return True
    return False
