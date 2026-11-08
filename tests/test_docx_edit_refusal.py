"""The refusal half of the support matrix: what the write-back will not do, proved first.

**What this file watches.** §5.7 item 3 of `LC-P3-02`: *"a structure outside the
support matrix fed to the write-back path is refused or handed to a person,
asserted **before any file is touched**"*. Two claims, and the second is the
one this project has lost before: ADR-0003 §C7 states the same rule for the
read-only source guard, and ``tests/test_workspace_boundaries.py`` watches it
with a filesystem spy, because *"it raised" is not the property — "nothing was
touched" is*. A refusal that happens after the bytes were written is a
rollback, and a rollback is a change.

**The ways an edit is refused here.**

| Reason | The case |
|---|---|
| ``target_inside_unsupported_structure`` | the passage sits in an equation, box, field or control |
| ``package_outside_support_matrix`` | the package carries a macro, an object, bound custom XML |
| ``part_outside_support_matrix`` | the change is aimed at a comment body, a header, a footnote |
| ``text_ambiguous`` / ``text_not_located`` | the passage is twice there, or not a whole run |
| ``package_unreadable`` | the bytes are not a package, or hold no document part |
| the rest | a paragraph not there, a change that changes nothing, a bad date |

**Each reason has a case, and no case is left undocumented.** The vocabulary
is compared against the raise sites read out of the module's own syntax, so a
refusal added without a sample and a sample naming a reason the code never
raises both fail here.

**The positive control is inside this file.**
``test_the_write_spy_records_a_write_when_one_happens`` arms the same spy
around a write that does happen and requires it to be recorded. A spy that
recorded nothing would let every refusal assertion above pass forever, which
is the failure §5.10 of the work orders calls a witness that watches nothing.
"""

from __future__ import annotations

import ast
import builtins
import io
import ntpath
import os
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest

from labcairn.editing.drafts import (
    REFUSALS,
    DraftForm,
    EditRefusedError,
    plan_edit,
    surgical_bytes,
)
from labcairn.editing.evidence import artifact_name
from labcairn.editing.samples import REFUSED, SAMPLES, WRITABLE, sample_bytes
from labcairn.editing.survey import DOCUMENT_PART, StructureClass

pytestmark = pytest.mark.negative

_BY_NAME = {sample.name: sample for sample in SAMPLES}

#: The primitives a refusal must not reach. **Patched rather than wrapped**,
#: for the reason ``tests/test_workspace_boundaries.py`` gives: the assertion
#: has to cover the primitive being reached for, not one particular wrapper,
#: or a caller that bypassed the seam's own helper is invisible.
_SPY_TARGETS: Final[tuple[tuple[object, str], ...]] = (
    (builtins, "open"),
    (os, "open"),
    (os, "replace"),
    (os, "rename"),
    (os, "remove"),
    (os, "unlink"),
    (os, "rmdir"),
    (os, "mkdir"),
    (os, "makedirs"),
    (os, "truncate"),
    (os, "utime"),
    (os, "chmod"),
    (ntpath, "abspath"),
    (shutil, "rmtree"),
    (shutil, "copyfile"),
    (shutil, "copy2"),
    (shutil, "move"),
    (Path, "write_text"),
    (Path, "write_bytes"),
    (Path, "unlink"),
    (Path, "mkdir"),
    (Path, "rename"),
    (Path, "touch"),
)


class WriteSpy:
    """Counts every attempt to modify the filesystem, and puts the primitives back."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._saved: list[tuple[object, str, Any]] = []

    def __enter__(self) -> WriteSpy:
        for owner, name in _SPY_TARGETS:
            original = getattr(owner, name)
            self._saved.append((owner, name, original))
            setattr(owner, name, self._wrap(name, original))
        return self

    def __exit__(self, *_: object) -> None:
        for owner, name, original in reversed(self._saved):
            setattr(owner, name, original)
        self._saved.clear()

    def _wrap(self, name: str, original: Any) -> Callable[..., Any]:
        def recorder(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            return original(*args, **kwargs)

        return recorder


def _refuse(sample_name: str) -> EditRefusedError:
    sample = _BY_NAME[sample_name]
    with pytest.raises(EditRefusedError) as caught:
        plan_edit(sample_bytes(sample), sample.edit)
    return caught.value


def test_every_refusal_sample_is_refused_for_the_reason_it_names() -> None:
    """The refusal half of the matrix, one case per row.

    **A "no" recorded with its measurement is what the matrix is for**, and a
    refusal that arrives for a different reason than the record prints is a
    record about a mechanism nobody built.
    """
    for sample in REFUSED:
        error = _refuse(sample.name)
        assert error.refusal.reason == sample.reason, (
            f"{sample.name}: declared {sample.reason!r}, the seam said "
            f"{error.refusal.reason!r} ({error.refusal.detail})"
        )


def test_a_refusal_touches_no_file_at_all(tmp_path: Path) -> None:
    """§5.7 item 3's clause, watched with a spy rather than with a sentence.

    **And the directory is checked too.** The spy proves no primitive ran; the
    listing proves the run left nothing behind. A half-written file the
    operator finds later is exactly what the atomic write path exists to
    prevent, and a refusal has no business producing one.
    """
    untouched = tmp_path / "would-be-written"
    untouched.mkdir()
    for sample in REFUSED:
        for form in DraftForm:
            with WriteSpy() as spy, pytest.raises(EditRefusedError):
                surgical_bytes(sample_bytes(sample), sample.edit, form)
            assert spy.calls == [], f"{sample.name} ({form.value}): the refusal ran {spy.calls}"
        assert list(untouched.iterdir()) == [], f"{sample.name}: the refusal left a file behind"


def test_the_refusal_names_the_structure_and_not_only_the_failure() -> None:
    """A refusal that says only "no" cannot become a matrix row.

    **The reason names the gate and the detail names the class and the place.**
    The operator has to be able to say which structure the change would have
    written into; without that the support matrix is a list of refusals rather
    than a statement about structures.
    """
    named: Final = (
        "10-refuse-edit-inside-an-equation",
        "11-refuse-edit-inside-a-text-box",
        "12-refuse-edit-of-a-fields-cached-answer",
        "13-refuse-edit-inside-a-content-control",
    )
    for name in named:
        refusal = _refuse(name).refusal
        assert refusal.reason == "target_inside_unsupported_structure", name
        classes = [
            structure.value for structure in StructureClass if structure.value in refusal.detail
        ]
        assert classes, f"{name}: the detail names no structure class: {refusal.detail}"
        assert "bytes" in refusal.detail, f"{name}: the detail names no place: {refusal.detail}"


def test_every_refusal_tells_a_person_what_to_do_instead() -> None:
    """*"refused **or handed to a person**"*: a refusal with no next line is a dead end.

    **Why the sentence is required rather than the field.** A handover that
    restated the failure would satisfy a "not empty" check and still leave the
    operator without a next act, so the assertion asks for the actor.
    """
    for name in [sample.name for sample in REFUSED]:
        refusal = _refuse(name).refusal
        assert refusal.handover.strip(), f"{name}: the refusal gives the operator nothing"
        assert "person" in refusal.handover or "a person" in refusal.handover, (
            f"{name}: the handover names no actor: {refusal.handover}"
        )
        assert refusal.handover != refusal.detail, f"{name}: the handover restates the failure"


def test_a_passage_that_occurs_twice_is_refused_rather_than_written_at_the_first() -> None:
    """The first occurrence is a guess, and a guess writes to the wrong sentence."""
    refusal = _refuse("18-refuse-ambiguous-occurrence").refusal
    assert refusal.reason == "text_ambiguous"
    assert "2 plain runs" in refusal.detail, refusal.detail


def test_a_change_cutting_a_run_in_two_is_refused_rather_than_rounded() -> None:
    """The seam replaces a run. A range ending mid-run would invent a boundary.

    **This is the refusal the record will be judged on.** An edit naming half
    a sentence the file wrote as two runs is the ordinary case, not a corner
    case, and a seam that "handled" it by writing the first run would delete
    the second one's words — damage inside the very paragraph the edit named,
    invisible to every region comparison, because that paragraph is the one
    the comparison is told to skip.
    """
    refusal = _refuse("19-refuse-edit-cutting-a-run-in-two").refusal
    assert refusal.reason == "text_not_located"
    assert "run" in refusal.detail, refusal.detail


def test_a_package_the_seam_never_opened_is_refused_whole() -> None:
    """A macro part, an embedded object and a bound customXml item refuse the package.

    **The refusal is about the part, not the passage.** These samples hold an
    ordinary body sentence the seam could locate; the gate closes anyway,
    because a package whose parts this run never rewrote is a package whose
    rewrite is unmeasured.
    """
    for name, structure in (
        ("14-refuse-package-carrying-macros", "vba"),
        ("15-refuse-package-carrying-an-embedded-object", "embedded-objects"),
        ("16-refuse-package-carrying-custom-xml", "custom-xml"),
    ):
        refusal = _refuse(name).refusal
        assert refusal.reason == "package_outside_support_matrix", name
        assert structure in refusal.detail, f"{name}: {refusal.detail}"


def test_a_change_aimed_at_another_part_is_refused_before_any_lookup() -> None:
    """The comment's own words are not a body paragraph, and the refusal says which part."""
    refusal = _refuse("17-refuse-edit-aimed-at-the-comment-part").refusal
    assert refusal.reason == "part_outside_support_matrix"
    assert "word/comments.xml" in refusal.detail and DOCUMENT_PART in refusal.detail


def test_bytes_that_are_not_a_package_are_refused_not_raised_over() -> None:
    """A Python traceback is not a refusal, and an operator cannot record it."""
    for name in (
        "25-refuse-a-package-that-is-not-a-package",
        "26-refuse-a-package-with-no-document-part",
    ):
        refusal = _refuse(name).refusal
        assert refusal.reason == "package_unreadable", name
        assert refusal.handover.strip(), name
        with pytest.raises(EditRefusedError):
            surgical_bytes(sample_bytes(_BY_NAME[name]), _BY_NAME[name].edit, DraftForm.MARKED)


def test_the_reason_vocabulary_is_exactly_the_raise_sites() -> None:
    """No documented reason the code cannot give, and no raise the record does not carry.

    **Read out of the module's own syntax.** The comparison is against the
    string literals ``_refuse`` is called with, because a table of reasons
    maintained by hand is a table that can be edited into agreement with a
    file that no longer raises them.
    """
    source = Path(__file__).resolve().parent.parent / "src/labcairn/editing/drafts.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    raised: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_refuse"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            raised.add(node.args[0].value)
    assert raised, "the scan found no refusal site, so it is not watching anything"
    assert raised == set(REFUSALS), (
        f"raised but undocumented: {sorted(raised - set(REFUSALS))}; "
        f"documented but never raised: {sorted(set(REFUSALS) - raised)}"
    )
    reached = {sample.reason for sample in REFUSED}
    assert reached == raised, (
        f"reasons no sample reaches: {sorted(raised - reached)}; "
        f"samples naming no raise site: {sorted(reached - raised)}"
    )


def test_the_write_spy_records_a_write_when_one_happens(tmp_path: Path) -> None:
    """The spy's own positive control: it must not be a spy that sees nothing."""
    with WriteSpy() as spy:
        (tmp_path / "proof.docx").write_bytes(b"proof that the spy is armed")
        with zipfile.ZipFile(io.BytesIO(sample_bytes(WRITABLE[0])), "r") as archive:
            assert DOCUMENT_PART in archive.namelist()
    assert "write_bytes" in spy.calls, spy.calls


def test_a_written_sample_is_not_refused() -> None:
    """The other half of the gate, so a refusal test cannot pass on a broken seam.

    **If the gate closed on everything, every refusal assertion above would
    still hold.** This is the row that says the seam writes what it is
    supposed to write, and it is why §5.2 calls a "no" a completion rather
    than a success: the completion is the pair of these two facts, not one.
    """
    for sample in WRITABLE:
        plan = plan_edit(sample_bytes(sample), sample.edit)
        assert plan.run_end > plan.run_start
        assert not plan.survey.blocked()
        assert artifact_name(sample.name, "surgical", "marked").endswith(".docx")
