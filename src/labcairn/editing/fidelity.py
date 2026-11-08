"""The fidelity measurement: what a rewrite left alone, compared rather than assumed.

**What this module answers.** §5.7 item 4 of the work orders asks for the
substitute-set round trip — *write, reopen, compare, with the original's hash
unchanged and the non-target regions compared rather than assumed*. "Compared
rather than assumed" is the whole design: a report that said "we did not touch
those parts" would be a restatement of the writer's intention, and the
intention of a whole-part serialiser is precisely the thing that fails.

**Three levels, because a `.docx` has three.**

* **package** — which parts changed at all: per-part content digest, entry
  order, entry metadata.
* **part** — which *regions* of the one rewritten part changed: a canonical
  digest per top-level body child, outside the edit.
* **file** — whether the product's own reader still sees the same history:
  :func:`labcairn.material.ooxml.read_document` over the produced bytes.

**Bytes and structure are reported apart.** Two arms change every byte of the
part they rewrite while changing no *meaning* in the regions they did not
target; one changes neither. Collapsing those into one column would let a
re-spelling pass as untouched and would hide the splice's real advantage, so
a region is `IDENTICAL` when its bytes match, `RESPELLED` when its canonical
tree matches and its bytes do not, and `CHANGED` when neither does.

**The prefix check is here because it is the host's question, asked locally.**
Word's ``mc:Ignorable`` and ``mc:Choice Requires`` attributes name prefixes,
and a serialiser that renames them breaks the promise without changing one
element. That is a machine-side fact, so it is measured here. Whether a given
host then shows a repair prompt is a human-side fact and belongs to the
reopen checklist, not to this module.
"""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ElementTree
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from labcairn.editing.drafts import ApprovedEdit, DraftForm, EditRefusedError, plan_edit
from labcairn.editing.survey import (
    CLASS_ELEMENTS,
    CLASS_PART_PATTERNS,
    DOCUMENT_PART,
    Spans,
    StructureClass,
    element_spans,
    root_open_tag,
)
from labcairn.material.ooxml import read_document

__all__ = [
    "OPTIONS",
    "ArmResult",
    "PartVerdict",
    "RegionStatus",
    "RegionVerdict",
    "all_part_class_spans",
    "canonical",
    "class_counts",
    "class_spans",
    "compare_classes",
    "compare_regions",
    "ignorables_missing",
    "part_inventory",
    "part_verdicts",
    "run_arm",
]


class RegionStatus(StrEnum):
    """What one region of a rewritten part turned out to be."""

    IDENTICAL = "IDENTICAL"
    RESPELLED = "RESPELLED"
    CHANGED = "CHANGED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class PartVerdict:
    """One package part, before and after."""

    name: str
    sha_before: str
    sha_after: str
    #: ``IDENTICAL``, ``RESPELLED``, ``CHANGED``, ``DROPPED`` or ``ADDED``,
    #: decided at *content* level: a part whose bytes differ but whose
    #: canonical tree matches was re-spelled, not rewritten.
    verdict: str


@dataclass(frozen=True)
class RegionVerdict:
    """One compared region: a top-level body child, or one structure class."""

    address: str
    status: RegionStatus
    detail: str = ""
    #: The structure class, for the rows :func:`compare_classes` produces, and
    #: ``""`` for the region rows, whose address already names the element.
    #: Two shapes share one row type because the matrix prints both tables from
    #: one column set, and a second type with the same fields would let the
    #: two drift apart while both still claimed to be the verdict.
    structure: str = ""


_PREFIX_DECLARATION: Final[re.Pattern[str]] = re.compile(r'xmlns:([A-Za-z0-9_]+)="[^"]*"')
_IGNORABLE: Final[re.Pattern[str]] = re.compile(r'mc:Ignorable="([^"]*)"')
_REQUIRED: Final[re.Pattern[str]] = re.compile(r'Requires="([^"]*)"')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def declaration(part: bytes) -> bytes:
    """The part's XML declaration, the bytes up to and including ``?>``.

    **Compared as bytes, not parsed.** A declaration is exactly the part of
    the file a parser is least obliged to keep, and the claim under test is
    whether the writer kept what the host wrote.
    """
    head = part[:200]
    end = head.find(b"?>")
    return head[: end + 2] if end != -1 else b""


def part_inventory(data: bytes) -> dict[str, bytes]:
    """Every part's bytes, in archive order."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


def entry_metadata(data: bytes) -> tuple[tuple[str, tuple[int, ...], int, int], ...]:
    """``(name, date_time, compress_type, create_system)`` per entry, in order.

    **Order included, because it is a claim.** A rewrite that alphabetised the
    parts would change the package's description of itself and would not be
    visible to a set comparison at all.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return tuple(
            (info.filename, info.date_time, info.compress_type, info.create_system)
            for info in archive.infolist()
        )


def canonical(element: ElementTree.Element) -> str:
    """A structural spelling of one element: URI, sorted attributes, text, children.

    **Why this is the comparison and not a text diff.** Two writers spell the
    same Word document differently — prefix names, declaration order,
    attribute quoting, whether an empty element is ``<a/>`` or ``<a></a>`` —
    and none of that is a change a reviewer would accept as "the sentence is
    the same". A canonical spelling keyed on namespace URIs and sorted
    attributes says *same tree*; the bytes say *same file*. Reporting both
    apart is what stops the two claims covering for each other.
    """
    attributes = " ".join(f"{key}={element.attrib[key]!r}" for key in sorted(element.attrib))
    text = (element.text or "").strip()
    tail = (element.tail or "").strip()
    children = "".join(f"{canonical(child)}|" for child in element)
    return f"{element.tag}[{attributes}]{text}[{children}]{tail}"


def _canonical_part(blob: bytes) -> str | None:
    try:
        return canonical(ElementTree.fromstring(blob))
    except ElementTree.ParseError:
        return None


def part_verdicts(
    before: Mapping[str, bytes], after: Mapping[str, bytes]
) -> tuple[PartVerdict, ...]:
    """Per-part verdicts over the whole package."""
    verdicts: list[PartVerdict] = []
    for name, blob in before.items():
        if name not in after:
            verdicts.append(PartVerdict(name, sha256(blob), "", "DROPPED"))
            continue
        produced = after[name]
        if blob == produced:
            verdict = "IDENTICAL"
        elif name.endswith((".xml", ".rels")) and _canonical_part(blob) == _canonical_part(
            produced
        ):
            verdict = "RESPELLED"
        else:
            verdict = "CHANGED"
        verdicts.append(PartVerdict(name, sha256(blob), sha256(produced), verdict))
    for name, blob in after.items():
        if name not in before:
            verdicts.append(PartVerdict(name, "", sha256(blob), "ADDED"))
    return tuple(verdicts)


def region_digests(part: bytes) -> dict[str, str]:
    """A canonical digest per top-level body child, keyed by its address.

    **The address form is the reader's**: ``w:p[3]`` is the third ``w:p``
    among the body's own children, which is how
    :func:`labcairn.material.ooxml._paragraph_path` names a paragraph, so a
    region in this report can be cited by the machinery that already cites
    text.
    """
    root = ElementTree.fromstring(part)
    body = next(child for child in root if child.tag.endswith("}body"))
    out: dict[str, str] = {}
    counters: dict[str, int] = {}
    for child in body:
        local = child.tag.rsplit("}", 1)[-1]
        counters[local] = counters.get(local, 0) + 1
        out[f"w:{local}[{counters[local]}]"] = canonical(child)
    return out


def _raw_region(part: bytes, address: str) -> bytes:
    """The bytes of one top-level body child, named by the same address form.

    **The test is the ancestor chain, two deep.** Every top-level region has
    ``w:document`` and ``w:body`` above it and nothing else, so a nested
    paragraph inside a text box cannot be mistaken for one — and a report that
    mistook them would be comparing the wrong bytes and calling the figure
    untouched.
    """
    local, _, index = address.partition("[")
    ordinal = int(index.rstrip("]"))
    named = [
        span
        for span in element_spans(part).every
        if span.ancestors == ("w:document", "w:body") and span.tag == local
    ]
    if ordinal > len(named):
        return b""
    span = named[ordinal - 1]
    return part[span.start : span.end]


def compare_regions(before_part: bytes, after_part: bytes, skip: str) -> tuple[RegionVerdict, ...]:
    """Every top-level body child except the edit's own region, compared.

    **The one region excluded is the one the edit named**, and the caller
    passes its address rather than guessing it here: the witness that this
    comparison is not vacuous is the one that asks whether the excluded region
    is the region containing the bytes the plan located.
    """
    before = region_digests(before_part)
    after = region_digests(after_part)
    verdicts: list[RegionVerdict] = []
    for address, digest in before.items():
        if address == skip:
            continue
        if address not in after:
            verdicts.append(RegionVerdict(address, RegionStatus.MISSING, "gone from the part"))
            continue
        if digest != after[address]:
            verdicts.append(RegionVerdict(address, RegionStatus.CHANGED, "tree differs"))
            continue
        raw_before, raw_after = _raw_region(before_part, address), _raw_region(after_part, address)
        if raw_before == raw_after:
            verdicts.append(RegionVerdict(address, RegionStatus.IDENTICAL, ""))
        else:
            verdicts.append(
                RegionVerdict(
                    address,
                    RegionStatus.RESPELLED,
                    f"bytes {len(raw_before)} to {len(raw_after)}, tree unchanged",
                )
            )
    for address in after:
        if address not in before and address != skip:
            verdicts.append(RegionVerdict(address, RegionStatus.CHANGED, "appeared in the part"))
    return tuple(verdicts)


def class_counts(data: bytes) -> dict[str, int]:
    """How many elements of each structure class the package holds.

    **Counts, not presence.** "The comments survived" and "the manuscript had
    three comments and now has two" are different claims, and the second is
    the one that matters when a rewrite is accused of eating a reviewer's
    work.
    """
    out: dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [info.filename for info in archive.infolist()]
        for structure, pattern in CLASS_PART_PATTERNS.items():
            hits = sum(1 for name in names if pattern.match(name))
            if hits:
                out[structure.value] = out.get(structure.value, 0) + hits
        for name in names:
            if not name.endswith((".xml", ".rels")):
                continue
            try:
                root = ElementTree.fromstring(archive.read(name))
            except ElementTree.ParseError:
                continue
            tags = [element.tag for element in root.iter()]
            for structure, elements in CLASS_ELEMENTS.items():
                hits = sum(1 for tag in tags if tag in elements)
                if hits:
                    out[structure.value] = out.get(structure.value, 0) + hits
    return out


def class_spans(part: bytes) -> Mapping[StructureClass, tuple[tuple[str, str, bytes], ...]]:
    """Every element of each structure class in one part: address, tree, bytes.

    **Address, tree and bytes together, because the matrix asks three
    questions of one region.** Is it still there (address); is it still the
    same structure (tree); was it left alone (bytes). A count answers only the
    first, and a count is what lets a re-spelling be reported as a
    preservation.
    """
    from labcairn.editing.survey import prefix_map

    root = ElementTree.fromstring(part)
    prefixes = prefix_map(part)
    spans = element_spans(part)
    out: dict[StructureClass, list[tuple[str, str, bytes]]] = {}
    for element in root.iter():
        for structure, elements in CLASS_ELEMENTS.items():
            if element.tag not in elements:
                continue
            out.setdefault(structure, []).append(
                (
                    _address(root, element),
                    canonical(element),
                    _raw_element(part, spans, element, prefixes),
                )
            )
    return {key: tuple(value) for key, value in out.items()}


def _address(root: ElementTree.Element, element: ElementTree.Element) -> str:
    """The element's ``tag[n]`` path, ``n`` its ordinal among siblings of its tag."""
    steps: list[str] = []
    current = element
    while current is not root:
        parent = _parent(root, current)
        if parent is None:
            break
        ordinal = 0
        for sibling in parent:
            if sibling.tag == current.tag:
                ordinal += 1
                if sibling is current:
                    break
        steps.append(f"{current.tag.rsplit('}', 1)[-1]}[{ordinal}]")
        current = parent
    steps.append(f"{root.tag.rsplit('}', 1)[-1]}[1]")
    steps.reverse()
    return "/" + "/".join(steps)


def _parent(root: ElementTree.Element, element: ElementTree.Element) -> ElementTree.Element | None:
    for candidate in root.iter():
        for child in candidate:
            if child is element:
                return candidate
    return None


def _raw_element(
    part: bytes, spans: Spans, element: ElementTree.Element, prefixes: Mapping[str, str]
) -> bytes:
    """The bytes of one element, found by matching its canonical spelling.

    **Matched rather than sliced from an offset ElementTree does not hand
    over.** The tree and the byte walk are two views of the same bytes and
    this is where they are joined: the walk's element whose resolved name and
    canonical spelling both equal the tree element's is that element. Two
    identical spellings of the same class then compare as the pair of
    spellings they are, which is what a structural comparison does anyway.
    """
    from labcairn.editing.survey import resolve_tag

    want = canonical(element)
    for span in spans.every:
        if resolve_tag(span.tag, prefixes) != element.tag:
            continue
        raw = part[span.start : span.end]
        try:
            if canonical(ElementTree.fromstring(raw)) == want:
                return raw
        except ElementTree.ParseError:
            continue
    return b""


def compare_classes(
    before: Mapping[StructureClass, tuple[tuple[str, str, bytes], ...]],
    after: Mapping[StructureClass, tuple[tuple[str, str, bytes], ...]],
    *,
    skip: str = "",
) -> tuple[RegionVerdict, ...]:
    """One verdict per structure class the document held, compared before and after.

    **The status is the worst thing the class suffered, not the average.**
    A class with one element re-spelled and one element unchanged is
    ``RESPELLED``: the claim a support-matrix row makes is that everything of
    that class came through, and one exception falsifies it. Averaging would
    turn a single lost equation into a percentage, and a percentage is how a
    loss gets carried forward instead of re-measured.

    **``skip`` is the located paragraph's path, and without it the row would
    be a lie about the edit's own act.** A marked draft adds two revision
    elements inside the paragraph it was told to change; counted as a class
    that "changed", the row would say the seam damaged tracked revisions when
    what it did was write the change a person approved. The same exclusion the
    region comparison makes, one level down.
    """

    def outside(address: str) -> bool:
        # An address is ``<part>:::<path>`` since the survey widened to every
        # XML part, so the skip is matched on the path the caller was given.
        tail = address.split(":::", 1)[-1]
        return not (skip and (tail == skip or tail.startswith(f"{skip}/")))

    verdicts: list[RegionVerdict] = []
    for structure in sorted(set(before) | set(after), key=str):
        name = structure.value
        left = tuple(row for row in before.get(structure, ()) if outside(row[0]))
        right = tuple(row for row in after.get(structure, ()) if outside(row[0]))
        if not left and right:
            verdicts.append(RegionVerdict(str(len(right)), RegionStatus.CHANGED, "appeared", name))
            continue
        if left and not right:
            verdicts.append(
                RegionVerdict(
                    address=str(len(left)),
                    status=RegionStatus.MISSING,
                    detail="gone",
                    structure=name,
                )
            )
            continue
        by_address = {address: (digest, raw) for address, digest, raw in right}
        identical = respelled = changed = 0
        for address, digest, raw in left:
            if address not in by_address:
                changed += 1
                continue
            other_digest, other_raw = by_address[address]
            if other_raw == raw:
                identical += 1
            elif other_digest == digest:
                respelled += 1
            else:
                changed += 1
        detail = f"{identical} identical, {respelled} respelled, {changed} changed of {len(left)}"
        if changed or identical + respelled != len(left):
            status = RegionStatus.CHANGED
        elif respelled:
            status = RegionStatus.RESPELLED
        else:
            status = RegionStatus.IDENTICAL
        verdicts.append(
            RegionVerdict(address=str(len(left)), status=status, detail=detail, structure=name)
        )
    return tuple(verdicts)


def ignorables_missing(part: bytes) -> tuple[str, ...]:
    """Prefixes ``mc:Ignorable`` or a ``Requires`` name but nothing declares.

    **The local half of the host's question.** A serialiser that renames
    ``w14`` to ``ns7`` leaves ``mc:Ignorable="w14"`` naming a prefix no one
    declares. This function finds that broken promise; it does not predict the
    repair dialog, which only a person in front of the host may record.
    """
    text = part.decode("utf-8", "replace")
    declared = set(_PREFIX_DECLARATION.findall(root_open_tag(part)))
    named: set[str] = set()
    for match in _IGNORABLE.findall(text):
        named.update(match.split())
    for match in _REQUIRED.findall(text):
        named.update(match.split())
    return tuple(sorted(named - declared))


def all_part_class_spans(
    data: bytes,
) -> Mapping[StructureClass, tuple[tuple[str, str, bytes], ...]]:
    """The class spans of every XML part, with the part name in the address.

    **A comment is carried in ``word/comments.xml``, not in the document.**
    Measuring only the document part made the reviewer's own words look
    unmeasured, and the honest reading of "carried" is: every part the edit
    did not name came back with the same elements in it.
    """
    merged: dict[StructureClass, list[tuple[str, str, bytes]]] = {}
    for name, blob in part_inventory(data).items():
        if not name.endswith((".xml", ".rels")):
            continue
        try:
            ElementTree.fromstring(blob)
        except ElementTree.ParseError:
            continue
        for structure, rows in class_spans(blob).items():
            merged.setdefault(structure, []).extend(
                # **The part name is a namespace on the address, not a path
                # segment.** ``word/comments.xml/comments[1]`` would be
                # ambiguous the moment a skip was matched by splitting on a
                # slash, and the slash is inside the part name.
                (f"{name}:::{address}", digest, raw)
                for address, digest, raw in rows
            )
    return {key: tuple(value) for key, value in merged.items()}


@dataclass(frozen=True)
class ArmResult:
    """Everything one option left measurable about one sample."""

    sample: str
    option: str
    form: str
    #: The refusal reason where the option produced nothing, else ``""``.
    refused: str
    original_sha256: str
    #: The hash of the manuscript bytes *after* the run. The seam never
    #: writes to them, so this equals :attr:`original_sha256` — and the
    #: witness that says so is why the field is carried rather than omitted.
    original_sha256_after: str
    parts: tuple[PartVerdict, ...]
    regions: tuple[RegionVerdict, ...]
    #: The same comparison one level down: per structure class the document
    #: held, which is what the support matrix prints as the ``carried`` column.
    classes: tuple[RegionVerdict, ...]
    counts_before: Mapping[str, int]
    counts_after: Mapping[str, int]
    ignorables: tuple[str, ...]
    reopened_comments: int
    reopened_revisions: int
    reopened_paragraphs: int
    reopened_problems: tuple[str, ...]
    #: The comment and revision inventories as the reader states them, so a
    #: lost reviewer is a line in a list and not a count that happens to match.
    reopened_inventory: tuple[str, ...]
    entry_order_kept: bool
    #: Whether the part still opens with the same XML declaration it arrived
    #: with. Word writes ``standalone="yes"`` and a serialiser that drops it
    #: changes the file's own statement about how it should be read, which is
    #: a container fact the host can care about even when no element changed.
    xml_declaration_kept: bool = True
    #: Bytes outside the located span, compared: ``True``/``False`` for an
    #: option with a span, ``None`` for one that never had one.
    untouched_bytes_equal: bool | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def produced(self) -> bool:
        return not self.refused

    def changed_parts(self) -> tuple[str, ...]:
        return tuple(part.name for part in self.parts if part.verdict != "IDENTICAL")

    def as_row(self) -> dict[str, object]:
        """The flat form the evidence report and the acceptance record print."""
        return {
            "sample": self.sample,
            "option": self.option,
            "form": self.form,
            "refused": self.refused,
            "original_sha256": self.original_sha256,
            "original_sha256_after": self.original_sha256_after,
            "parts": {p.name: p.verdict for p in self.parts},
            "changed_parts": list(self.changed_parts()),
            "regions": {r.address: r.status.value for r in self.regions},
            "classes": {r.structure: r.status.value for r in self.classes},
            "class_detail": {r.structure: r.detail for r in self.classes},
            "counts_before": dict(self.counts_before),
            "counts_after": dict(self.counts_after),
            "ignorables_missing": list(self.ignorables),
            "reopened": {
                "comments": self.reopened_comments,
                "revisions": self.reopened_revisions,
                "paragraphs": self.reopened_paragraphs,
                "problems": list(self.reopened_problems),
            },
            "entry_order_kept": self.entry_order_kept,
            "xml_declaration_kept": self.xml_declaration_kept,
            "untouched_bytes_equal": self.untouched_bytes_equal,
            "notes": list(self.notes),
        }


def _refused(
    sample: str,
    option: str,
    form: DraftForm,
    original: bytes,
    reason: str,
    detail: str,
) -> ArmResult:
    """The result an option gets when it produced nothing.

    **Counts are read defensively.** An input that is not a package has no
    class table, and a report that crashed while describing a refusal would
    be a report that cannot describe the most important refusal of all.
    """
    reopened = read_document(original)
    try:
        counts = class_counts(original)
    except (zipfile.BadZipFile, OSError):
        counts = {}
    return ArmResult(
        sample=sample,
        option=option,
        form=form.value,
        refused=reason,
        original_sha256=sha256(original),
        original_sha256_after=sha256(original),
        parts=(),
        regions=(),
        classes=(),
        counts_before=counts,
        counts_after=counts,
        ignorables=(),
        reopened_comments=len(reopened.comments),
        reopened_revisions=len(reopened.revisions),
        reopened_paragraphs=len(reopened.paragraphs),
        reopened_problems=tuple(problem.code for problem in reopened.problems),
        reopened_inventory=_inventory(reopened),
        entry_order_kept=True,
        untouched_bytes_equal=None,
        notes=(detail,),
    )


def _writer(option: str) -> Callable[[bytes, ApprovedEdit, DraftForm], bytes]:
    """The named option's writer, resolved late so an arm may be unavailable.

    **Resolved by name, and late.** The library option imports python-docx
    inside its own function, so a run that asks for ``surgical`` never pays
    for lxml, and a run that asks for ``library`` reports what the library
    did rather than what was assumed of it.
    """
    if option == "surgical":
        from labcairn.editing.drafts import surgical_bytes

        return surgical_bytes
    if option == "reserialize":
        from labcairn.editing.reserialize import reserialize_bytes

        def _reserialize(data: bytes, edit: ApprovedEdit, form: DraftForm) -> bytes:
            del form  # option B has no way to write a tracked change; see its module
            return reserialize_bytes(data, edit)

        return _reserialize
    if option == "library":
        from labcairn.editing.library import library_edit_bytes

        def _library(data: bytes, edit: ApprovedEdit, form: DraftForm) -> bytes:
            del form  # option C has no model for a tracked change; see its module
            return library_edit_bytes(data, edit.old_text, edit.new_text)

        return _library
    if option == "rebuild":
        from labcairn.editing.rebuild import rebuild_bytes

        def _rebuild(data: bytes, edit: ApprovedEdit, form: DraftForm) -> bytes:
            del form
            return rebuild_bytes(data, edit)

        return _rebuild
    raise KeyError(f"no rewrite option is named {option!r}")


#: The options the record compares. ``surgical`` is the adopted one; the
#: others are the ones it had to price before choosing.
OPTIONS: Final[tuple[str, ...]] = ("surgical", "reserialize", "library", "rebuild")


def run_arm(
    sample: str,
    original: bytes,
    edit: ApprovedEdit,
    option: str,
    form: DraftForm,
    *,
    skip_region: str | None = None,
) -> ArmResult:
    """One option over one sample: write, reopen, compare.

    **The refusal is a result, not an absence.** A refused arm is reported
    with its reason and with the unchanged hash of the manuscript, because
    §5.10 names a row left blank as the same defect as a witness deleted in a
    merge.
    """
    write = _writer(option)
    notes: list[str] = []
    try:
        plan = plan_edit(original, edit)
    except EditRefusedError as exc:
        # **The refusal is reported, not raised on.** The gate closes first,
        # so nothing here has read a part list or opened a package: an input
        # that is not a package at all is answered with a reason, which is
        # what §5.7 item 3 asks of it, and the unchanged digest of the bytes
        # that were handed in is the record that nothing was produced.
        return _refused(sample, option, form, original, exc.refusal.reason, exc.refusal.detail)

    try:
        produced = write(original, edit, form)
    except (EditRefusedError, LookupError, ValueError) as exc:
        # **An option that cannot do the act reports that, rather than doing
        # something else.** The rebuild and library arms raise when the file
        # they were handed has no paragraph the arm's own model can address;
        # that is a measured limit of the option, and it belongs in the report
        # as a refusal with the option's name on it, not as a stack trace.
        return _refused(sample, option, form, original, f"{type(exc).__name__}", str(exc))

    before = part_inventory(original)
    after = part_inventory(produced)
    reopened = read_document(produced)
    skipped = (
        skip_region
        if skip_region is not None
        else _region_of(before[DOCUMENT_PART], plan.run_start)
    )
    untouched: bool | None = None
    if option == "surgical":
        source, result = before[DOCUMENT_PART], after[DOCUMENT_PART]
        tail = len(source) - plan.run_end
        untouched = source[: plan.run_start] == result[: plan.run_start] and (
            source[plan.run_end :] == result[len(result) - tail :]
        )
    notes.append(f"skipped region {skipped}")
    return ArmResult(
        sample=sample,
        option=option,
        form=form.value,
        refused="",
        original_sha256=sha256(original),
        original_sha256_after=sha256(original),
        parts=part_verdicts(before, after),
        regions=compare_regions(before[DOCUMENT_PART], after[DOCUMENT_PART], skip=skipped),
        classes=compare_classes(
            all_part_class_spans(original),
            all_part_class_spans(produced),
            skip=_class_skip(before[DOCUMENT_PART], plan.run_start),
        ),
        counts_before=class_counts(original),
        counts_after=class_counts(produced),
        ignorables=ignorables_missing(after[DOCUMENT_PART]),
        reopened_comments=len(reopened.comments),
        reopened_revisions=len(reopened.revisions),
        reopened_paragraphs=len(reopened.paragraphs),
        reopened_problems=tuple(problem.code for problem in reopened.problems),
        reopened_inventory=_inventory(reopened),
        entry_order_kept=[name for name, _, _, _ in entry_metadata(produced)]
        == [name for name, _, _, _ in entry_metadata(original)],
        xml_declaration_kept=declaration(before[DOCUMENT_PART])
        == declaration(after[DOCUMENT_PART]),
        untouched_bytes_equal=untouched,
        notes=tuple(notes),
    )


def _class_skip(part: bytes, offset: int) -> str:
    """The located paragraph's path in the form :func:`class_spans` addresses elements by.

    **Two spellings of one address, and the seam has to speak both.** The
    region table says ``w:p[2]`` because it walks the body's children; the
    class table says ``/document[1]/body[1]/p[2]/ins[1]`` because it walks
    every element from the root. A skip that was not translated would exclude
    nothing, and the edit's own inserted revision would be counted as damage
    to the revision class.
    """
    region = _region_of(part, offset)
    if not region:
        return ""
    local, _, index = region.partition("[")
    return f"/document[1]/body[1]/{local.removeprefix('w:')}[{index.rstrip(']')}]"


def _region_of(part: bytes, offset: int) -> str:
    """The address of the top-level body child holding ``offset``."""
    counters: dict[str, int] = {}
    for span in element_spans(part).every:
        if span.ancestors != ("w:document", "w:body"):
            continue
        counters[span.tag] = counters.get(span.tag, 0) + 1
        if span.start <= offset < span.end:
            return f"{span.tag}[{counters[span.tag]}]"
    return ""


def _inventory(document: object) -> tuple[str, ...]:
    """The reader's own statement of what it found, as sorted strings.

    **The point is to compare the history, not the count.** Two documents can
    hold three revisions each and not be the same three, so an inventory
    naming kind, author and text is what a real loss fails against.
    """
    from labcairn.material.ooxml import RevisionDocument

    assert isinstance(document, RevisionDocument)
    rows = [
        f"revision:{event.kind}:{event.author or '-'}:{event.text}" for event in document.revisions
    ]
    rows += [
        f"comment:{event.comment_id}:{event.author or '-'}:{event.text}"
        for event in document.comments
    ]
    return tuple(sorted(rows))
