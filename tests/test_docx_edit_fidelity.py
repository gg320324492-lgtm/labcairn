"""The substitute-set round trip: write, reopen, compare, and prove the comparison bites.

**What this file watches.** `LC-P3-02` §5.7 item 4 asks for the round trip --
write, reopen, compare, with the original's hash unchanged and the non-target
regions compared rather than assumed. Both halves are watched here, and the
second one is watched twice: once over the four rewrite options, and once
against a difference that was put in on purpose. A comparison that has never
been shown a difference is a comparison that cannot be trusted to have found
none, and the project has said this before of its own harnesses.

**The options, and what each one is for.**

| Option | What it does | Why it is run |
|---|---|---|
| ``surgical`` | replace one element's bytes, carry the rest | the candidate the record adopts |
| ``reserialize`` | rewrite the tree, serialise the part again | the cheapest local alternative |
| ``library`` | open with python-docx and save what it writes | the declared library's own cost |
| ``rebuild`` | write a fresh document from the read text | the shape the project already ships |

**Why the rows are built once.** The measurement is the one the report prints;
a generator is spent by the first test that walks it and the rest would see
nothing and pass, which is the quiet failure §5.10 names.

**Why the numbers are recomputed rather than remembered.** Every assertion
runs the measurement again. The counts printed in
``docs/acceptance/LC-P3-02-support-matrix.md`` are checked against a fresh run
by ``tests/test_docx_edit_records.py``: a number carried forward from an
earlier tree is a number about that earlier tree.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass

import pytest

from labcairn.editing.drafts import DraftForm, plan_edit, read_part, splice, surgical_bytes
from labcairn.editing.fidelity import (
    ArmResult,
    RegionStatus,
    class_spans,
    compare_classes,
    compare_regions,
    part_inventory,
    run_arm,
)
from labcairn.editing.samples import SAMPLES, WRITABLE, Sample, sample_bytes
from labcairn.editing.survey import DOCUMENT_PART, element_spans
from labcairn.material.ooxml import read_document

pytestmark = pytest.mark.integration

BY_NAME: dict[str, Sample] = {sample.name: sample for sample in SAMPLES}
COMPOSITE: str = "07-everything-at-once"


@dataclass(frozen=True)
class Row:
    """One sample, one form, the bytes it started from and the result it produced."""

    sample: Sample
    form: DraftForm
    data: bytes
    result: ArmResult

    @property
    def label(self) -> str:
        return f"{self.sample.name} ({self.form.value})"


@pytest.fixture(scope="module")
def surgical_rows() -> list[Row]:
    """One row per written sample per form, from the adopted option."""
    rows: list[Row] = []
    for sample in WRITABLE:
        data = sample_bytes(sample)
        for form in DraftForm:
            rows.append(
                Row(
                    sample=sample,
                    form=form,
                    data=data,
                    result=run_arm(sample.name, data, sample.edit, "surgical", form),
                )
            )
    return rows


def test_the_surgical_seam_changes_the_document_part_and_nothing_else(
    surgical_rows: list[Row],
) -> None:
    """Every part the edit did not name is carried byte for byte.

    **This is the claim §5.1 is about.** A manuscript is a package, and the
    reviewer's words, the figure's bytes and the equation's markup live in
    parts the edit was not told about. If one of them changed, that change is
    damage, whatever the diff of the sentence says.
    """
    for row in surgical_rows:
        changed = [part.name for part in row.result.parts if part.verdict != "IDENTICAL"]
        assert changed == [DOCUMENT_PART], (
            f"{row.label}: the seam changed {changed}; it may change "
            f"{DOCUMENT_PART} and nothing else"
        )


def test_the_original_manuscript_is_never_the_file_that_is_written(
    surgical_rows: list[Row],
) -> None:
    """§5.7 item 4, first clause: the original's hash is unchanged, every time."""
    for row in surgical_rows:
        assert row.result.original_sha256 == row.result.original_sha256_after, (
            f"{row.label}: the manuscript bytes moved during the write"
        )
        assert hashlib.sha256(row.data).hexdigest() == row.result.original_sha256


def test_the_bytes_outside_the_located_element_are_the_same_bytes(
    surgical_rows: list[Row],
) -> None:
    """Not "the same information": the same bytes, before the cut and after it.

    **Why this is stated at byte level.** The part-level test above can pass
    while a serialiser re-spells everything inside the one part it rewrote.
    This is the test that separates the splice from the serialiser, and it is
    why the record adopts the splice.
    """
    for row in surgical_rows:
        assert row.result.untouched_bytes_equal is True, f"{row.label}: bytes outside the run moved"


def test_the_regions_the_edit_did_not_name_are_left_identical(
    surgical_rows: list[Row],
) -> None:
    """The same claim one level down: every top-level body child but the edited one."""
    for row in surgical_rows:
        assert row.result.regions, f"{row.label}: the region comparison compared nothing"
        offenders = [
            (region.address, region.status.value, region.detail)
            for region in row.result.regions
            if region.status is not RegionStatus.IDENTICAL
        ]
        assert not offenders, f"{row.label}: regions came back different: {offenders}"


def test_the_structure_classes_the_document_held_all_survived_the_write(
    surgical_rows: list[Row],
) -> None:
    """Comments, revisions, tables, equations, images, boxes, fields, controls, links.

    **Element by element, not "present" by class.** A manuscript that held two
    comments and now holds one has lost a reviewer's work, and a presence test
    would not see it.
    """
    for row in surgical_rows:
        offenders = [
            f"{line.structure}: {line.status.value} ({line.detail})"
            for line in row.result.classes
            if line.status is not RegionStatus.IDENTICAL
        ]
        assert not offenders, f"{row.label}: classes that did not survive: {offenders}"


def test_the_marked_draft_records_the_change_as_a_tracked_revision(
    surgical_rows: list[Row],
) -> None:
    """The marked draft is read back through the reader, not through the writer.

    **The accepted view must read the approved words, the rejected view must
    still read the sentence the change replaced, and the revision the reader
    reports must carry the product's author and the injected date.** A writer
    that said it had marked the change and a reader that could not see the
    mark is the defect this whole ticket exists to avoid.
    """
    seen = 0
    for row in surgical_rows:
        if row.form is not DraftForm.MARKED:
            continue
        seen += 1
        document = read_document(surgical_bytes(row.data, row.sample.edit, DraftForm.MARKED))
        index = row.sample.edit.paragraph - 1
        assert row.sample.edit.new_text in document.paragraphs[index], (
            f"{row.label}: the accepted view does not read the approved text"
        )

        before_document = read_document(row.data)
        assert document.baseline_paragraphs[index] == before_document.baseline_paragraphs[index], (
            f"{row.label}: the rejected view moved. A marked draft may add a change "
            "a reviewer can take back; it may not change what the document said "
            "before anyone approved anything"
        )
        ours = [event for event in document.revisions if event.author == row.sample.edit.author]
        assert {event.kind for event in ours} == {"ins", "del"}, (
            f"{row.label}: the marked draft carries {[(e.kind, e.text) for e in ours]}"
        )
        assert all(event.date is not None for event in ours), f"{row.label}: a mark with no date"
    assert seen == len(WRITABLE), f"only {seen} marked drafts were examined"


def test_the_clean_draft_matches_the_approved_edit_and_carries_no_mark(
    surgical_rows: list[Row],
) -> None:
    """The other export form: the approved sentence, and nothing saying it moved."""
    for row in surgical_rows:
        if row.form is not DraftForm.CLEAN:
            continue
        document = read_document(surgical_bytes(row.data, row.sample.edit, DraftForm.CLEAN))
        index = row.sample.edit.paragraph - 1
        before = read_document(row.data).paragraphs[index]
        expected = before.replace(row.sample.edit.old_text, row.sample.edit.new_text, 1)
        assert document.paragraphs[index] == expected, (
            f"{row.label}: the clean draft does not read as the approved edit"
        )
        assert before != document.paragraphs[index], (
            f"{row.label}: the clean draft changed nothing it can be seen to change"
        )
        marks = [event for event in document.revisions if event.author == row.sample.edit.author]
        assert not marks, f"{row.label}: the clean draft carries a mark"


#: The one reader problem this run accepts as a consequence of a write, and
#: the sample it is accepted on. **A waiver with no name attached is how a
#: regression becomes background noise**, so the pair is asserted together.
NESTED_REVISION_SAMPLE: str = "09-target-inside-another-reviewers-insertion"


def test_the_reopened_file_gives_the_reader_no_unexpected_problem(
    surgical_rows: list[Row],
) -> None:
    """A rewrite the product's own reader cannot parse is not a fidelity-preserving edit.

    **One problem code is expected, and it is named here rather than waived.**
    An edit aimed at a run sitting inside another reviewer's insertion writes a
    revision inside a revision, and the reader reports ``docx_nested_revision``
    for that document before and after: the nesting is in the sample, not in
    the rewrite. The assertion is therefore that the rewrite introduced no
    code the original did not already carry.
    """
    for row in surgical_rows:
        before = {problem.code for problem in read_document(row.data).problems}
        reopened = read_document(surgical_bytes(row.data, row.sample.edit, row.form))
        after = {problem.code for problem in reopened.problems}
        added = after - before
        if added == {NESTED_PROBLEM}:
            assert row.sample.name == NESTED_REVISION_SAMPLE and row.form is DraftForm.MARKED, (
                f"{row.label}: the nested-revision report appeared outside the one "
                "sample and form it is documented for"
            )
            continue
        assert not added, f"{row.label}: the reader found {sorted(added)} after the write"


def test_the_declaration_and_the_entry_order_survive_the_surgical_write(
    surgical_rows: list[Row],
) -> None:
    """What the host wrote around the parts, not only inside them."""
    for row in surgical_rows:
        assert row.result.entry_order_kept, f"{row.label}: the part order moved"
        assert row.result.xml_declaration_kept, f"{row.label}: the XML declaration moved"
        assert not row.result.ignorables, (
            f"{row.label}: undeclared prefixes {row.result.ignorables}"
        )


# --------------------------------------------------------------------------- #
# the other options: measured, not described
# --------------------------------------------------------------------------- #


def test_reserialising_the_part_re_spells_regions_the_edit_did_not_name() -> None:
    """Option B's cost in one count: the tree survives, some bytes do not.

    **This is a measurement that decided something.** "We only changed the one
    paragraph" is true of the structure and false of the bytes for whichever
    regions the serialiser re-spells, and a host reads bytes. The splice is
    adopted because it is the option where both halves of that sentence are
    true on every sample.
    """
    respelled = 0
    identical = 0
    for sample in WRITABLE:
        data = sample_bytes(sample)
        for form in DraftForm:
            result = run_arm(sample.name, data, sample.edit, "reserialize", form)
            for region in result.regions:
                if region.status is RegionStatus.RESPELLED:
                    respelled += 1
                elif region.status is RegionStatus.IDENTICAL:
                    identical += 1
            assert all(line.status is RegionStatus.IDENTICAL for line in result.classes), (
                f"{sample.name}: option B changed a structure's tree, not only its spelling"
            )
            assert not result.xml_declaration_kept, (
                f"{sample.name}: option B kept the XML declaration, so it is not "
                "being measured as the serialiser it is"
            )
    assert respelled > 0 and identical > 0, (
        f"option B returned {respelled} respelled and {identical} identical regions; "
        "one of the two columns is not being exercised"
    )


def test_reserialising_drops_a_prefix_the_documents_own_attributes_still_name() -> None:
    """The markup-compatibility promise is the finding that rejects option B.

    **Why this is a measured claim and not a warning.** Word's
    ``mc:Ignorable`` and ``mc:Choice Requires`` attributes name prefixes *by
    spelling*. A serialiser that stops declaring a prefix one of those
    attributes names leaves a document whose own compatibility promise points
    at nothing. The report prints which prefix, on how many artifacts, and
    under which options, so the claim can be re-checked against the run.
    """
    offenders: list[tuple[str, tuple[str, ...]]] = []
    for sample in WRITABLE:
        data = sample_bytes(sample)
        for option in ("surgical", "reserialize", "library"):
            result = run_arm(sample.name, data, sample.edit, option, DraftForm.CLEAN)
            if result.ignorables:
                offenders.append((f"{sample.name}/{option}", result.ignorables))
    assert offenders, (
        "no option broke an mc-named prefix, so the prefix column of the report "
        "is measuring nothing and the claim about it is unchecked"
    )
    surgical = [name for name, _ in offenders if name.endswith("/surgical")]
    assert not surgical, f"the adopted option broke these promises: {surgical}"


def test_the_library_option_rewrites_parts_the_seam_carries() -> None:
    """Option C's cost: the document's regions can survive and the package does not."""
    widened = 0
    for sample in WRITABLE:
        data = sample_bytes(sample)
        result = run_arm(sample.name, data, sample.edit, "library", DraftForm.CLEAN)
        changed = {part.name for part in result.parts if part.verdict != "IDENTICAL"}
        if changed - {DOCUMENT_PART}:
            widened += 1
        assert changed == {DOCUMENT_PART} or len(changed) > 1, (
            f"{sample.name}: the library changed exactly one part, so the comparison "
            "stopped separating it from the splice"
        )
    assert widened == len(WRITABLE), (
        f"the library widened the write on {widened} of {len(WRITABLE)}"
    )


def test_the_rebuild_option_loses_the_structures_it_never_read() -> None:
    """Option D's cost, stated as counts: the sentence survives, the manuscript does not."""
    losses = 0
    for sample in WRITABLE:
        data = sample_bytes(sample)
        result = run_arm(sample.name, data, sample.edit, "rebuild", DraftForm.CLEAN)
        losses += sum(1 for line in result.classes if line.status is RegionStatus.MISSING)
    assert losses >= 5, f"only {losses} classes vanished across the rebuild arm"


# --------------------------------------------------------------------------- #
# the comparison has teeth
# --------------------------------------------------------------------------- #


NESTED_PROBLEM: str = "docx_nested_revision"


def test_a_marked_draft_inside_another_reviewers_insertion_nests_the_revision() -> None:
    """The finding the nested-revision waiver is about, stated as a claim.

    **Why it is written down rather than smoothed over.** The paragraph the
    change lands in is itself inside Dr. Zhao's insertion, so the product's
    deletion and insertion sit inside another author's insertion. The reader
    reports that as ``docx_nested_revision``, which LC-P2-07's corpus already
    established is representable: the outer revision decides what the two
    views hold. Both views are unchanged in meaning by the write, so this is
    not damage; it is a document whose host rendering of a nested revision is
    a §4.9 row, and the matrix says so.
    """
    sample = BY_NAME[NESTED_REVISION_SAMPLE]
    data = sample_bytes(sample)
    marked = surgical_bytes(data, sample.edit, DraftForm.MARKED)
    document = read_document(marked)
    assert NESTED_PROBLEM in {problem.code for problem in document.problems}
    ours = [event for event in document.revisions if event.author == sample.edit.author]
    assert {event.kind for event in ours} == {"ins", "del"}
    assert all(event.nested for event in ours), "the product's revision is not nested"
    original = read_document(data)
    assert document.paragraphs[1] == original.paragraphs[1].replace(
        sample.edit.old_text, sample.edit.new_text, 1
    ), "the accepted view did not take the approved change"
    assert document.baseline_paragraphs[1] == original.baseline_paragraphs[1], (
        "the rejected view moved: the outer insertion decides what both views hold, "
        "and the mark has to leave that decision where the reviewer put it"
    )
    clean = read_document(surgical_bytes(data, sample.edit, DraftForm.CLEAN))
    assert NESTED_PROBLEM not in {problem.code for problem in clean.problems}, (
        "the clean draft nests nothing, so the report is about the mark and not the text"
    )


def test_the_region_comparison_fails_when_a_region_was_really_changed() -> None:
    """A difference put in on purpose is found, or every IDENTICAL above is unfalsified.

    **Why the damage is done outside the seam.** The point is not to test the
    splice again; it is to show that the table the report prints distinguishes
    "left alone" from "rewritten". A helper that damaged the bytes the edit
    *was* allowed to change would prove nothing, so this rewrites a closing
    sentence no edit was ever given.
    """
    sample = BY_NAME[COMPOSITE]
    data = sample_bytes(sample)
    produced = surgical_bytes(data, sample.edit, DraftForm.MARKED)
    clean = compare_regions(
        part_inventory(data)[DOCUMENT_PART], part_inventory(produced)[DOCUMENT_PART], "w:p[1]"
    )
    assert all(region.status is RegionStatus.IDENTICAL for region in clean), clean

    damaged = _rezip(produced, _damage_a_paragraph(part_inventory(produced)[DOCUMENT_PART]))
    compared = compare_regions(
        part_inventory(data)[DOCUMENT_PART], part_inventory(damaged)[DOCUMENT_PART], "w:p[1]"
    )
    offenders = [
        region.address for region in compared if region.status is not RegionStatus.IDENTICAL
    ]
    assert offenders == [_closing_region_address(part_inventory(data)[DOCUMENT_PART])], (
        f"the comparison reported {offenders} after the closing sentence was rewritten"
    )


def test_the_class_comparison_fails_when_a_class_was_really_lost() -> None:
    """The same teeth at the class level, where the support matrix's rows come from."""
    sample = BY_NAME[COMPOSITE]
    data = sample_bytes(sample)
    produced = surgical_bytes(data, sample.edit, DraftForm.CLEAN)
    before = part_inventory(data)[DOCUMENT_PART]
    after = part_inventory(produced)[DOCUMENT_PART]
    skip = "/document[1]/body[1]/p[1]"
    assert all(
        line.status is RegionStatus.IDENTICAL
        for line in compare_classes(class_spans(before), class_spans(after), skip=skip)
    )
    dropped = _drop_the_equation(after)
    rows = compare_classes(class_spans(before), class_spans(dropped), skip=skip)
    equations = [line for line in rows if line.structure == "equations"]
    assert equations and equations[0].status is RegionStatus.MISSING, (
        f"deleting an equation did not reach the equations row: {rows}"
    )


def test_the_region_the_comparison_skips_is_the_region_the_seam_wrote() -> None:
    """The exclusion is the plan's own byte span, not a name someone typed.

    **This is what makes every "IDENTICAL" above honest.** Each region
    comparison leaves one region out; if the region left out were not the one
    the seam wrote, a real change could hide inside the skip. So the located
    span is turned into its region address here, that region is damaged, and
    the comparison is run twice -- once skipping the address the plan implies,
    once skipping nothing.
    """
    for sample in WRITABLE:
        data = sample_bytes(sample)
        plan = plan_edit(data, sample.edit)
        part = read_part(data, DOCUMENT_PART)
        children = [
            span for span in element_spans(part).every if span.ancestors == ("w:document", "w:body")
        ]
        region = next(span for span in children if span.start <= plan.run_start < span.end)
        ordinal = sum(
            1 for span in children if span.tag == region.tag and span.start <= region.start
        )
        address = f"{region.tag}[{ordinal}]"

        damaged_region = _swap_text(part[region.start : region.end])
        damaged = _rezip(data, part[: region.start] + damaged_region + part[region.end :])
        damaged_part = read_part(damaged, DOCUMENT_PART)

        skipped = compare_regions(part, damaged_part, skip=address)
        left = [row.address for row in skipped if row.status is not RegionStatus.IDENTICAL]
        assert not left, f"{sample.name}: skipping {address} still reported {left}"
        unskipped = compare_regions(part, damaged_part, skip="")
        offenders = [row.address for row in unskipped if row.status is not RegionStatus.IDENTICAL]
        assert offenders == [address], f"{sample.name}: damaging {address} reported {offenders}"


def test_the_splice_helper_moves_nothing_outside_the_range_it_is_given() -> None:
    """One line of the seam, watched on its own.

    **Because everything above depends on it and it depends on nothing.** The
    splice is the fidelity claim; the rest of the module decides where to cut.
    A witness that only exercised the splice through a whole rewrite could not
    tell a moved byte from a re-spelled one.
    """
    part = b"<a><keep/><b>old</b><keep2/></a>"
    start = part.index(b"old")
    end = start + len(b"old")
    assert splice(part, start, end, b"new") == b"<a><keep/><b>new</b><keep2/></a>"
    assert splice(part, 0, 0, b"x") == b"x" + part
    assert splice(part, len(part), len(part), b"y") == part + b"y"
    assert splice(part, 0, len(part), b"<z/>") == b"<z/>"
    assert part == b"<a><keep/><b>old</b><keep2/></a>", "the splice mutated its input bytes"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _closing_region_address(part: bytes) -> str:
    """The body-child address of the paragraph holding :data:`TAIL_TEXT`."""
    children = [
        span
        for span in element_spans(part).every
        if span.ancestors == ("w:document", "w:body") and TAIL_TEXT in part[span.start : span.end]
    ]
    assert len(children) == 1, children
    span = children[0]
    siblings = [
        other
        for other in element_spans(part).every
        if other.ancestors == ("w:document", "w:body") and other.tag == span.tag
    ]
    ordinal = siblings.index(span) + 1
    return f"{span.tag}[{ordinal}]"


TAIL_TEXT: bytes = b"The closing sentence rounds the paragraph set off."


def _swap_text(region: bytes) -> bytes:
    """Rewrite the first text node inside one region's bytes."""
    swapped = re.sub(
        rb"(<w:t[^>]*>)([^<]*)(</w:t>)",
        rb"\g<1>somebody else wrote this\g<3>",
        region,
        count=1,
    )
    assert swapped != region, "the region held no text node to swap"
    return swapped


def _damage_a_paragraph(part: bytes) -> bytes:
    """Rewrite the closing sentence -- a region no edit was ever given."""
    damaged = re.sub(
        rb"<w:t[^>]*>The closing sentence rounds the paragraph set off\.</w:t>",
        b"<w:t>The closing sentence was rewritten by someone else.</w:t>",
        part,
        count=1,
    )
    assert damaged != part, "the damage helper found nothing to damage"
    return damaged


def _drop_the_equation(part: bytes) -> bytes:
    damaged = re.sub(rb"<m:oMathPara>.*?</m:oMathPara>", b"", part, count=1, flags=re.S)
    assert damaged != part, "the composite sample carried no display equation to drop"
    return damaged


def _rezip(produced: bytes, part: bytes) -> bytes:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(produced)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            payload = part if info.filename == DOCUMENT_PART else source.read(info.filename)
            carried = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            carried.compress_type = info.compress_type
            carried.create_system = info.create_system
            target.writestr(carried, payload)
    return out.getvalue()
