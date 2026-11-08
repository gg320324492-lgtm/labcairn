"""The edit contract, the plan, and the splice that writes one element.

**What this module is for.** `LC-P3-02` §5.1 asks whether the product can put
an approved change into an **existing** manuscript without damaging what it
did not touch. This module answers that for the option the record adopts:
locate one element's bytes, replace them, change nothing else in the
package. :mod:`labcairn.editing.fidelity` is the measurement that says
whether that claim holds, and :mod:`labcairn.editing.reserialize`,
:mod:`labcairn.editing.library` and :mod:`labcairn.editing.rebuild` are the
options it is compared against.

**Bytes in, bytes out — no path, no file.** Every function here takes a
manuscript's bytes and returns bytes. That is not tidiness.
`src/labcairn/workspace/outputs.py` is the only place in the product that
writes a file, the path-length question around it is §7 of the work orders,
and this ticket owns neither. A seam that returns bytes cannot open a file
at all, so *"the refusal happens before any file is touched"* stops being a
claim about an order of operations and becomes a property of the type.

**Why the located unit is a run and not a character range.** A range that
ended in the middle of a run would have the seam invent a run boundary the
file does not have — and an invented boundary is a structural change to the
region the edit was said not to touch. So an edit names the **whole text of
one plain run**, and a change that would cut a run in half is refused rather
than approximated.

**Why two forms and not one.** A marked draft records the change as a
tracked revision, so the host can see who proposed it and take it back; a
clean draft writes it in as ordinary text, which is what execution plan §4's
*"the clean draft matches the approved edits"* speaks of. Both come from one
plan, so the difference between them is the mark and nothing else.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from labcairn.editing.survey import (
    DOCUMENT_PART,
    TAG_CLASS,
    UNEDITABLE_CLASSES,
    PackageSurvey,
    Span,
    Spans,
    StructureClass,
    element_spans,
    element_text,
    inside_field,
    survey,
)

__all__ = [
    "ApprovedEdit",
    "DraftForm",
    "EditRefusedError",
    "Plan",
    "Refusal",
    "clean_payload",
    "draft_bytes",
    "marked_payload",
    "package_bytes_with_part",
    "plan_edit",
    "read_part",
    "splice",
    "surgical_bytes",
]

#: The date form ``w:date`` carries: ISO-8601 with an offset. Checked rather
#: than trusted, because a date Word cannot parse is a repair prompt with our
#: author name on it.
_DATE: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

#: Every spelling of the revision-id attribute the byte scan will treat as
#: taken. A document may carry ``w:id`` and ``w14:id``; both are integers
#: Word keeps unique, and a collision ties two changes together.
_ID_ATTRIBUTE: Final[re.Pattern[bytes]] = re.compile(rb'[A-Za-z0-9]+:id="(-?\d+)"')

_PRESERVE: Final[str] = 'xml:space="preserve"'


class DraftForm(StrEnum):
    """The two exports one approved edit produces."""

    MARKED = "marked"
    CLEAN = "clean"


@dataclass(frozen=True)
class Refusal:
    """Why the write-back produces no bytes, and what a person does instead.

    ``reason`` is the code a support-matrix row carries; ``handover`` is the
    sentence the operator is given, because §5.7 item 3 says *"refused **or
    handed to a person**"*. A refusal with no next sentence is a dead end,
    and a dead end is how an operator learns to work around a gate.
    """

    reason: str
    detail: str
    handover: str


class EditRefusedError(Exception):
    """The plan was refused. Raised before any byte of output exists."""

    def __init__(self, refusal: Refusal) -> None:
        super().__init__(f"{refusal.reason}: {refusal.detail}")
        self.refusal = refusal


@dataclass(frozen=True)
class ApprovedEdit:
    """One change a person has approved, addressed the way the reader addresses text.

    ``paragraph`` is the 1-based ordinal of a ``w:p`` in document order —
    the numbering :func:`labcairn.material.ooxml.read_document` uses, so the
    same number names the same paragraph in the reader and in the seam.
    ``old_text`` is the **whole** text of one plain run inside it.
    """

    part: str
    paragraph: int
    old_text: str
    new_text: str
    author: str
    #: ISO-8601 with an offset, the way ``w:date`` carries it. Never read
    #: from the clock: a test that stamps the wall clock cannot reproduce
    #: its own bytes an hour later.
    date: str


@dataclass(frozen=True)
class Plan:
    """One located element, and what will be written in its place."""

    edit: ApprovedEdit
    survey: PackageSurvey
    #: Byte span of the located run within the part.
    run_start: int
    run_end: int
    #: The run's element name **as written** — the seam spells everything it
    #: emits with the prefix the file already uses, because a prefix is how
    #: ``mc:Ignorable`` and ``mc:Choice Requires`` name what they mean.
    run_tag: str
    #: The run's ``w:rPr`` bytes verbatim, or ``b""`` when it carried none:
    #: copying them is what keeps this sentence's formatting while the
    #: sentence changes.
    run_properties: bytes
    #: The located text with the escapes resolved, for the deletion payload.
    old_text: str
    #: Two fresh ids that collide with no id already in the part. A tuple of
    #: any length, because :func:`_free_ids` is written for "some ids" and a
    #: fixed-length annotation would let the function and the type disagree.
    revision_ids: tuple[str, ...]


def _refuse(reason: str, detail: str, handover: str) -> EditRefusedError:
    return EditRefusedError(Refusal(reason=reason, detail=detail, handover=handover))


def read_part(data: bytes, name: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return archive.read(name)
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise _refuse(
            "package_unreadable",
            f"the package gives no {name} to plan against: {type(exc).__name__}: {exc}",
            "re-import the manuscript; nothing was written",
        ) from exc


def _free_ids(part: bytes, wanted: int) -> tuple[str, ...]:
    """``wanted`` revision ids, smallest first, colliding with none in the part."""
    taken = {int(match) for match in _ID_ATTRIBUTE.findall(part)}
    out: list[str] = []
    candidate = 1
    while len(out) < wanted:
        if candidate not in taken:
            out.append(str(candidate))
        candidate += 1
    return tuple(out)


def _children(parent: Span, spans: Spans) -> tuple[Span, ...]:
    """The elements whose parent **is this element**, not one like it.

    **Depth and containment, both.** Every run spells ``w:r``, so a check on
    the parent's *tag* would make one run a child of another run somewhere
    else in the document as soon as the two overlap by bytes — which a text
    box guarantees: the box's run sits inside the body run that carries the
    drawing. Tag equality alone then reads the box's text node as the body
    sentence's, and the seam edits a figure's caption believing it wrote a
    paragraph. ``depth == parent.depth + 1`` plus containment makes the
    relation a fact about this tree, not about a name.
    """
    return tuple(
        span
        for span in spans.every
        if parent.holds(span) and span.depth == parent.depth + 1 and span is not parent
    )


def run_text_nodes(run: Span, spans: Spans) -> tuple[Span, ...]:
    """The ``w:t`` nodes of one run, direct children only, in document order.

    **Only ``w:t``.** ``w:delText`` sits inside a ``w:del`` and belongs to
    the rejected view; treating it as a run's text would let an edit replace
    words the file says are already deleted, which is the read side's
    two-view rule thrown away on the way to the write.
    """
    return tuple(child for child in _children(run, spans) if child.tag == "w:t")


def run_text(part: bytes, run: Span, spans: Spans) -> str:
    """The text a run carries, its escapes resolved."""
    return "".join(element_text(part, span) for span in run_text_nodes(run, spans))


def run_is_plain(run: Span, spans: Spans) -> bool:
    """Whether the run is its properties and exactly one text node, nothing else.

    **What disqualifies a run.** A second text node means a break or a tab
    sits between them, and a ``w:tab`` or ``w:br`` child says the same thing
    in the file's own words. Either way the splice would drop it, and
    dropping a tab is a change to a region the edit did not name.
    """
    if len(run_text_nodes(run, spans)) != 1:
        return False
    return all(child.tag in {"w:rPr", "w:t"} for child in _children(run, spans))


def plan_edit(data: bytes, edit: ApprovedEdit) -> Plan:
    """Locate the element an edit replaces, or refuse, producing no bytes.

    **The order of the checks is the claim.** The package is surveyed before
    a single element is located: a manuscript the seam must not rewrite at
    all — one carrying a macro part, or a change aimed at a header — is
    refused without the seam ever claiming it found the passage. Location
    comes second, and the region's own structure third. Nothing here opens a
    file, so a refusal has no side effect to undo.
    """
    if not _DATE.match(edit.date):
        raise _refuse(
            "date_not_iso_8601",
            f"the edit stamps w:date {edit.date!r}, which is not ISO-8601 with an offset",
            "a person re-stamps the edit from the injected clock",
        )

    try:
        package_survey = survey(data)
    except ValueError as exc:
        # **The package is refused, not raised over.** ``survey`` reports bytes
        # that are not a Word package — the same finding the read side calls
        # ``docx_unreadable`` — in a ``ValueError``. Letting it escape would
        # reach the operator as a traceback and be recorded as a refusal
        # nowhere, and §5.7 item 3 asks for a refusal with a name.
        raise _refuse(
            "package_unreadable",
            str(exc),
            "a person re-imports the manuscript; the write-back produced no bytes",
        ) from exc

    if edit.part != DOCUMENT_PART:
        raise _refuse(
            "part_outside_support_matrix",
            f"the edit is aimed at {edit.part} and the seam rewrites {DOCUMENT_PART} only",
            "hand the change to a person: a header, a footer and a comment body are "
            "not body paragraphs, and this run measured no part but the document",
        )

    blocked = sorted(package_survey.blocked(), key=str)
    if blocked:
        where = "; ".join(
            f"{structure.value} in {', '.join(package_survey.seen_in.get(structure, ('?',)))}"
            for structure in blocked
        )
        raise _refuse(
            "package_outside_support_matrix",
            f"the package carries {', '.join(s.value for s in blocked)} ({where}): "
            "carried through the substitute rewrite, never opened by it",
            "hand the file to a person and record the change as a remark, so a macro "
            "or a bound part is not silently rewritten",
        )

    if edit.old_text == edit.new_text:
        raise _refuse(
            "edit_changes_nothing",
            "the approved text is the text already there",
            "a person records the approval without a write",
        )

    part = read_part(data, edit.part)
    spans = element_spans(part)
    if not 1 <= edit.paragraph <= len(spans.paragraphs):
        raise _refuse(
            "paragraph_absent",
            f"the part holds {len(spans.paragraphs)} paragraphs and the edit names "
            f"number {edit.paragraph}",
            "a person re-reads the manuscript and re-addresses the edit",
        )

    paragraph = spans.paragraphs[edit.paragraph - 1]
    candidates = [run for run in spans.runs_inside(paragraph) if run_is_plain(run, spans)]

    if not candidates:
        raise _refuse(
            "paragraph_holds_no_plain_run",
            f"paragraph {edit.paragraph} holds no run carrying exactly one plain text "
            "node, so there is nothing the seam can replace",
            "hand the paragraph to a person: the seam has nothing there to replace",
        )

    matches = [run for run in candidates if run_text(part, run, spans) == edit.old_text]
    if not matches:
        raise _refuse(
            "text_not_located",
            f"no plain run in paragraph {edit.paragraph} carries the whole text the "
            "edit names: the seam replaces a run, never part of one",
            "re-read the paragraph and re-address the edit, or hand it to a person",
        )
    if len(matches) > 1:
        raise _refuse(
            "text_ambiguous",
            f"the text occurs in {len(matches)} plain runs of paragraph "
            f"{edit.paragraph}, and a seam that wrote to the first would be guessing "
            "which occurrence the reviewer meant",
            "widen the edit's text until one occurrence answers, or hand it to a person",
        )

    run = matches[0]
    inside = {TAG_CLASS[tag] for tag in (*run.ancestors, run.tag) if tag in TAG_CLASS}
    if inside_field(run, spans):
        inside = inside | {StructureClass.FIELDS}
    refused = sorted(inside & UNEDITABLE_CLASSES, key=str)
    if refused:
        raise _refuse(
            "target_inside_unsupported_structure",
            f"the located run sits inside {', '.join(s.value for s in refused)} at "
            f"bytes {run.start}-{run.end}: the seam emits plain runs and this run "
            "never measured emitting that structure",
            f"hand paragraph {edit.paragraph} to a person so the host rewrites the "
            "structure itself",
        )

    return Plan(
        edit=edit,
        survey=package_survey,
        run_start=run.start,
        run_end=run.end,
        run_tag=run.tag,
        run_properties=_properties(part, run, spans),
        old_text=edit.old_text,
        revision_ids=_free_ids(part, 2),
    )


def _properties(part: bytes, run: Span, spans: Spans) -> bytes:
    """The located run's ``w:rPr`` bytes, verbatim, or ``b""``."""
    for child in _children(run, spans):
        if child.tag == "w:rPr":
            return part[child.start : child.end]
    return b""


def _prefix(run_tag: str) -> str:
    """``w:r`` → ``w:``: the prefix the file already uses, or ``""``."""
    return run_tag.split(":", 1)[0] + ":" if ":" in run_tag else ""


def escape(text: str) -> str:
    """Escape text for a text node: the three characters that can break one.

    A quote inside ``<w:t>`` is not special and escaping it would put a
    backslash-free but pointless ``&quot;`` in the reviewer's sentence.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def marked_payload(plan: Plan) -> bytes:
    """The edit as a tracked change: the old text deleted, the new text inserted.

    **The run's own properties are copied into both branches.** A reviewer
    who bolded a phrase and then approved a wording change should not get
    the bold back only after they accept it.
    """
    prefix = _prefix(plan.run_tag)
    run = f"{prefix}r"
    props = plan.run_properties.decode("utf-8")
    delete_id, insert_id = plan.revision_ids
    stamp = f'{prefix}author="{escape(plan.edit.author)}" {prefix}date="{escape(plan.edit.date)}"'
    deleted = (
        f'<{prefix}del {stamp} {prefix}id="{delete_id}">'
        f"<{run}>{props}<{prefix}delText {_PRESERVE}>{escape(plan.old_text)}</{prefix}delText>"
        f"</{run}></{prefix}del>"
    )
    inserted = (
        f'<{prefix}ins {stamp} {prefix}id="{insert_id}">'
        f"<{run}>{props}<{prefix}t {_PRESERVE}>{escape(plan.edit.new_text)}</{prefix}t>"
        f"</{run}></{prefix}ins>"
    )
    return f"{deleted}{inserted}".encode()


def clean_payload(plan: Plan) -> bytes:
    """The edit as ordinary text, with no mark that anything was ever changed."""
    prefix = _prefix(plan.run_tag)
    run = f"{prefix}r"
    props = plan.run_properties.decode("utf-8")
    return (
        f"<{run}>{props}<{prefix}t {_PRESERVE}>{escape(plan.edit.new_text)}</{prefix}t></{run}>"
    ).encode()


def splice(part: bytes, start: int, end: int, payload: bytes) -> bytes:
    """Replace ``part[start:end]`` with ``payload`` and touch no other byte.

    **This one line is the seam's fidelity claim**, which is why it is a
    function of its own with a witness of its own: everything else in this
    module decides *where* to cut, and this decides that nothing else moves.
    """
    return part[:start] + payload + part[end:]


def package_bytes_with_part(original: bytes, name: str, replacement: bytes) -> bytes:
    """The package with one part replaced and every other entry carried verbatim.

    **Entry order, dates, compression type, attributes and the creator
    system come from the source entry's own ``ZipInfo``.** A package that
    re-sorted its parts or restamped their dates would put a difference in
    every file the edit did not name, and the fidelity report would then be
    measuring the container rather than the seam.
    """
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(original)) as source,
        zipfile.ZipFile(out, "w") as target,
    ):
        for info in source.infolist():
            payload = replacement if info.filename == name else source.read(info.filename)
            carried = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            carried.compress_type = info.compress_type
            carried.external_attr = info.external_attr
            carried.internal_attr = info.internal_attr
            carried.create_system = info.create_system
            carried.create_version = info.create_version
            carried.comment = info.comment
            target.writestr(carried, payload)
    return out.getvalue()


def surgical_bytes(data: bytes, edit: ApprovedEdit, form: DraftForm) -> bytes:
    """Plan the edit and write it, in one call, for a caller that has no plan yet.

    **The two-step form stays.** :func:`plan_edit` is the half that can refuse
    and the half that touches nothing, and an operator who wants to show a
    person the plan before any bytes exist uses it directly. This is the
    convenience over the pair, for the measurement harness.
    """
    return draft_bytes(data, plan_edit(data, edit), form)


def draft_bytes(data: bytes, plan: Plan, form: DraftForm) -> bytes:
    """The manuscript with the planned edit written in one of the two forms."""
    part = read_part(data, plan.edit.part)
    payload = marked_payload(plan) if form is DraftForm.MARKED else clean_payload(plan)
    return package_bytes_with_part(
        data, plan.edit.part, splice(part, plan.run_start, plan.run_end, payload)
    )


#: The refusal reasons the seam can give, and the class each names. The
#: support matrix prints this list, and ``tests/test_docx_edit_records.py``
#: reddens when a reason appears here that no witness produces: a refusal
#: nothing exercises is a refusal that will be refactored away.
REFUSALS: Final[Mapping[str, str]] = {
    "date_not_iso_8601": "the edit's own stamp is not the form the format declares",
    "part_outside_support_matrix": "the change is aimed at a part the seam does not rewrite",
    "package_outside_support_matrix": "the package carries a part class never rewritten here",
    "edit_changes_nothing": "there is no change to write",
    "package_unreadable": "the bytes are not a package the seam can plan against",
    "paragraph_absent": "the address names no paragraph",
    "paragraph_holds_no_plain_run": ("the paragraph holds nothing a run splice can replace"),
    "text_not_located": "the passage is not the whole text of any one run",
    "text_ambiguous": ("the passage occurs more than once, so the seam would be guessing"),
    "target_inside_unsupported_structure": (
        "the passage sits inside a class the seam may carry but not write"
    ),
}
