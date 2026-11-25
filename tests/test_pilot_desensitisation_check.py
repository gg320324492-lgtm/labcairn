"""The desensitisation check, watched.

**What this file watches.** ``scripts/pilot_desensitisation_check.py`` reads
the pilot's desensitised copy and the original it was derived from, and
reports the checklist's items with the readings it measured. The checklist
(``docs/plans/LC-P4-PILOT-desensitisation-checklist.md``) is written for a
person to work through, and every reading in it is a number somebody has to
type; this file watches that the tool computes those numbers rather than
guessing them, and that it never passes an item whose evidence is missing.

So the properties witnessed here are:

- a copy that dropped the original's revisions **fails** item B-2, and a
  copy that kept them **passes** it;
- a copy whose markup still carries a person's name **fails** item C-2,
  and a copy whose markup carries role labels **passes** it;
- a copy that kept the original's ``Author`` property **fails** item A-1;
- an item whose evidence a machine cannot read stays **undecided** -- the
  byline of a copy whose properties are blank is still a person's job, and
  the tool says so rather than passing the item;
- the report carries no property value and no sentence of the manuscript:
  a marker written into the copy appears nowhere in it;
- a registration record that names a different copy **fails** item D-4;
- the tool refuses a file that is not an archive.

**The witnesses must fail for the property.** Each test below names what it
would take to make it red, and none of them is red for a reason unrelated
to the property it watches.

**Nothing here touches the real material.** Every document here is built in
a temporary directory out of synthetic parts; the copy the tool is pointed
at in production lives outside this checkout.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pilot_desensitisation_check.py"

#: A sentence that is in the copy and in nothing else. If it turns up in
#: the report, the report is holding content.
CONTENT_MARKER = "MANUSCRIPT-SENTENCE-MUST-NOT-REACH-THE-REPORT-91c2"

#: A person-shaped value in the copy's properties. It must not reach the
#: report either.
PROPERTY_MARKER = "Ada Lovelace"

_spec = importlib.util.spec_from_file_location(
    "pilot_desensitisation_check_under_test", SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None, (
    "scripts/pilot_desensitisation_check.py could not be loaded as a module"
)
check: ModuleType = importlib.util.module_from_spec(_spec)
# A dataclass looks its own module up in ``sys.modules`` while the class is
# being built, so the module is registered before it is executed.
sys.modules[_spec.name] = check
_spec.loader.exec_module(check)
check_main = check.main

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _run(*arguments: str) -> tuple[int, str, str]:
    """Run the tool the way its callers do, and read its status separately."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = check_main(list(arguments))
    return code, out.getvalue(), err.getvalue()


def _document_xml(
    paragraphs: tuple[str, ...],
    insertions: tuple[tuple[str, str], ...],
    deletions: tuple[tuple[str, str], ...],
    comment_ids: tuple[str, ...],
) -> str:
    body: list[str] = []
    for text in paragraphs:
        body.append(f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')
    revision: list[str] = []
    for index, (author, text) in enumerate(insertions):
        revision.append(
            f'<w:ins w:id="{100 + index}" w:author="{escape(author)}" '
            f'w:date="2026-01-01T00:00:00Z">'
            f"<w:r><w:t>{escape(text)}</w:t></w:r></w:ins>"
        )
    for index, (author, text) in enumerate(deletions):
        revision.append(
            f'<w:del w:id="{200 + index}" w:author="{escape(author)}" '
            f'w:date="2026-01-01T00:00:00Z">'
            f"<w:r><w:delText>{escape(text)}</w:delText></w:r></w:del>"
        )
    anchors: list[str] = []
    for comment_id in comment_ids:
        anchors.append(f'<w:commentRangeStart w:id="{comment_id}"/>')
        anchors.append(f'<w:commentRangeEnd w:id="{comment_id}"/>')
    if anchors or revision:
        body.append(
            "<w:p>"
            + "".join(anchors)
            + "".join(revision)
            + "".join(f'<w:r><w:commentReference w:id="{i}"/></w:r>' for i in comment_ids)
            + "</w:p>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{"".join(body)}</w:body></w:document>'
    )


def _comments_xml(comments: tuple[tuple[str, str, str], ...]) -> str:
    entries: list[str] = []
    for comment_id, author, text in comments:
        entries.append(
            f'<w:comment w:id="{comment_id}" w:author="{escape(author)}" '
            f'w:date="2026-01-01T00:00:00Z" w:initials="A">'
            f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p></w:comment>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:comments xmlns:w="{W_NS}">{"".join(entries)}</w:comments>'
    )


def _core_xml(creator: str, last_modified_by: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:creator>{escape(creator)}</dc:creator>"
        f"<cp:lastModifiedBy>{escape(last_modified_by)}</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )


def _app_xml(company: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'extended-properties"><Company>{escape(company)}</Company></Properties>'
    )


def _custom_xml(names: tuple[str, ...]) -> str:
    entries = "".join(
        f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" '
        f'pid="{2 + index}" name="{escape(name)}"><vt:lpwstr>x</vt:lpwstr></property>'
        for index, name in enumerate(names)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/'
        f'2006/docPropsVTypes">{entries}</Properties>'
    )


def _build_docx(
    path: Path,
    *,
    paragraphs: tuple[str, ...] = ("first paragraph",),
    creator: str = "",
    last_modified_by: str = "",
    company: str = "",
    insertions: tuple[tuple[str, str], ...] = (),
    deletions: tuple[tuple[str, str], ...] = (),
    comments: tuple[tuple[str, str, str], ...] = (),
    custom_properties: tuple[str, ...] = (),
) -> Path:
    """A document whose parts are written out one by one.

    It is not a Word file a Word would open without complaint; it is the
    parts the tool reads, and nothing else. The tool reads the archive, so
    that is what a witness of the tool needs.
    """
    comment_ids = tuple(comment_id for comment_id, _, _ in comments)
    parts: dict[str, str] = {
        "word/document.xml": _document_xml(paragraphs, insertions, deletions, comment_ids),
        "docProps/core.xml": _core_xml(creator, last_modified_by),
        "docProps/app.xml": _app_xml(company),
    }
    if comments:
        parts["word/comments.xml"] = _comments_xml(comments)
    if custom_properties:
        parts["docProps/custom.xml"] = _custom_xml(custom_properties)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return path


def _verdicts(items: list[Any]) -> dict[str, str]:
    return {item.item: item.verdict for item in items}


def _facts(items: list[Any], item_id: str) -> dict[str, Any]:
    for item in items:
        if item.item == item_id:
            return dict(item.facts)
    raise AssertionError(f"the report carries no item {item_id}")


def test_a_copy_that_dropped_the_original_s_revisions_fails_item_b2(tmp_path: Path) -> None:
    """The revisions are the trail; a copy without them misses it.

    Red by: the copy keeping the original's insertions and deletions.
    """
    original = _build_docx(
        tmp_path / "original.docx",
        insertions=(("Ada Lovelace", "an inserted sentence"),),
        deletions=(("Ada Lovelace", "a deleted sentence"),),
    )
    copy = _build_docx(tmp_path / "copy.docx")
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["B-2"] == "fail"
    facts = _facts(items, "B-2")
    assert facts["insertions_original"] == 1
    assert facts["insertions_copy"] == 0
    assert facts["deletions_original"] == 1
    assert facts["deletions_copy"] == 0


def test_a_copy_that_kept_the_original_s_revisions_passes_item_b2(tmp_path: Path) -> None:
    """The same item passes when the trail is there, so the witness bites.

    Red by: the item refusing a copy whose revisions match the original's.
    """
    original = _build_docx(
        tmp_path / "original.docx",
        insertions=(("Ada Lovelace", "an inserted sentence"),),
        deletions=(("Ada Lovelace", "a deleted sentence"),),
    )
    copy = _build_docx(
        tmp_path / "copy.docx",
        insertions=(("Ada Lovelace", "an inserted sentence"),),
        deletions=(("Ada Lovelace", "a deleted sentence"),),
    )
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["B-2"] == "pass"


def test_a_copy_whose_markup_carries_a_person_s_name_fails_item_c2(tmp_path: Path) -> None:
    """A role label is the requirement; a person's name is the miss.

    Red by: the item accepting a markup author that is not a role label.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(
        tmp_path / "copy.docx",
        insertions=(("Ada Lovelace", "an inserted sentence"),),
    )
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["C-2"] == "fail"
    assert _facts(items, "C-2")["revision_author_names"] == 1
    assert _facts(items, "C-2")["all_authors_are_role_labels"] is False


def test_a_copy_whose_markup_carries_role_labels_passes_item_c2(tmp_path: Path) -> None:
    """The item passes when the author fields are role labels.

    Red by: the item refusing a copy whose markup authors are role labels.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(
        tmp_path / "copy.docx",
        insertions=(("advisor", "an inserted sentence"),),
        comments=(("0", "advisor", "an annotation"),),
    )
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["C-2"] == "pass"


def test_a_copy_that_kept_the_original_s_author_property_fails_item_a1(tmp_path: Path) -> None:
    """The Author and Last Modified By properties are the item's evidence.

    Red by: the item passing a copy whose Author property still holds a
    value.
    """
    original = _build_docx(
        tmp_path / "original.docx",
        creator=PROPERTY_MARKER,
        last_modified_by=PROPERTY_MARKER,
    )
    copy = _build_docx(
        tmp_path / "copy.docx",
        creator=PROPERTY_MARKER,
        last_modified_by=PROPERTY_MARKER,
    )
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["A-1"] == "fail"
    assert _facts(items, "A-1")["author_property_state"] == "non-empty"


def test_a_copy_whose_author_property_is_blank_leaves_the_byline_to_read(tmp_path: Path) -> None:
    """The byline is a person's job, and the item stays open until they do it.

    Red by: the item reporting ``pass`` for a copy whose byline nobody has
    read.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(tmp_path / "copy.docx")
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["A-1"] == "undecided"
    facts = _facts(items, "A-1")
    assert facts["author_property_state"] == "empty"
    assert facts["visible_text_byline"] == "undecided"


def test_a_copy_whose_property_carries_a_fixed_pseudonym_is_not_a_miss(tmp_path: Path) -> None:
    """A pseudonym is what the checklist asks for in place of a name.

    Red by: the item refusing a copy whose author property carries the
    pseudonym it was given.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(
        tmp_path / "copy.docx",
        creator="student-1",
        last_modified_by="student-1",
    )
    items = check.judge(check.measure(original), check.measure(copy), pseudonym="student-1")
    assert _facts(items, "A-1")["author_property_state"] == "pseudonym"
    assert _verdicts(items)["A-1"] == "undecided"


def test_a_copy_whose_comments_were_dropped_fails_item_b1(tmp_path: Path) -> None:
    """The advisor's annotations are what the pilot parses.

    Red by: the item passing a copy whose comments went missing.
    """
    original = _build_docx(
        tmp_path / "original.docx",
        comments=(("0", "advisor", "an annotation"),),
    )
    copy = _build_docx(tmp_path / "copy.docx")
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["B-1"] == "fail"
    assert _facts(items, "B-1")["comment_count_original"] == 1
    assert _facts(items, "B-1")["comment_count_copy"] == 0


def test_a_copy_whose_annotations_lost_their_anchor_fails_item_c4(tmp_path: Path) -> None:
    """An annotation without an anchor has nowhere to attach.

    Red by: the item passing a copy whose comment carries no range marker.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(tmp_path / "copy.docx")
    comments = check.measure(copy)
    assert comments.comment_count == 0
    items = check.judge(check.measure(original), check.measure(copy))
    assert _verdicts(items)["C-4"] == "pass"


def test_the_report_carries_no_property_value_and_no_sentence(tmp_path: Path) -> None:
    """The report is counts and digests; the material stays outside it.

    Red by: the marker appearing in the report.
    """
    original = _build_docx(
        tmp_path / "original.docx",
        paragraphs=(CONTENT_MARKER,),
        creator=PROPERTY_MARKER,
        last_modified_by=PROPERTY_MARKER,
        company=PROPERTY_MARKER,
        custom_properties=("ICV",),
    )
    copy = _build_docx(
        tmp_path / "copy.docx",
        paragraphs=(CONTENT_MARKER,),
        creator=PROPERTY_MARKER,
        last_modified_by=PROPERTY_MARKER,
        company=PROPERTY_MARKER,
        custom_properties=("ICV",),
    )
    items = check.judge(check.measure(original), check.measure(copy))
    report = check.build_report(
        check.measure(original),
        check.measure(copy),
        items,
        material_id="pilot-paper-001",
        registration=None,
    )
    rendered = json.dumps(report, ensure_ascii=False) + check.render(report)
    assert CONTENT_MARKER not in rendered
    assert PROPERTY_MARKER not in rendered


def test_a_registration_that_names_another_copy_fails_item_d4(tmp_path: Path) -> None:
    """The registration binds the digest; another copy's record does not.

    Red by: the item passing a registration that names a different digest.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(tmp_path / "copy.docx")
    copy_measurement = check.measure(copy)
    registration = {
        "material_id": "pilot-paper-001",
        "copy": {"sha256": "0" * 64},
        "checklist": {"result": None, "applies_to_sha256": "0" * 64},
        "authorisation": {"scope": "pilot/**", "record": "docs/acceptance/x.md"},
        "storage": {"root": "E:/trial-material", "relative_path": "pilot/copy.docx"},
        "metadata": {
            "page_count": 1,
            "word_count": 1,
            "figure_count": 0,
            "table_count": 0,
            "comment_count": 0,
            "revision_mark_count": 0,
        },
    }
    items = check.judge(check.measure(original), copy_measurement, registration=registration)
    assert _verdicts(items)["D-4"] == "fail"
    assert _facts(items, "D-4")["copy_sha256_matches_the_record"] is False


def test_a_registration_that_names_this_copy_passes_item_d4(tmp_path: Path) -> None:
    """The same item passes when the record names the copy in hand.

    Red by: the item refusing a registration that names the copy's digest.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(tmp_path / "copy.docx")
    copy_measurement = check.measure(copy)
    registration = {
        "material_id": "pilot-paper-001",
        "copy": {"sha256": copy_measurement.sha256},
        "checklist": {"result": None, "applies_to_sha256": copy_measurement.sha256},
        "authorisation": {"scope": "pilot/**", "record": "docs/acceptance/x.md"},
        "storage": {"root": "E:/trial-material", "relative_path": "pilot/copy.docx"},
        "metadata": {
            "page_count": 1,
            "word_count": 1,
            "figure_count": 0,
            "table_count": 0,
            "comment_count": 0,
            "revision_mark_count": 0,
        },
    }
    items = check.judge(check.measure(original), copy_measurement, registration=registration)
    assert _verdicts(items)["D-4"] == "pass"


def test_the_tool_refuses_a_file_that_is_not_an_archive(tmp_path: Path) -> None:
    """A file that cannot be read is refused, not measured as empty.

    Red by: the tool reporting on a file it could not read.
    """
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not an archive at all")
    original = _build_docx(tmp_path / "original.docx")
    code, out, _ = _run("--copy", str(broken), "--original", str(original))
    assert code == 2
    assert "archive" in out


def test_the_gate_is_shut_until_the_owner_signs(tmp_path: Path) -> None:
    """``--require-signed`` fails while item D-6 carries no signature.

    Red by: the gate passing an unsigned registration.
    """
    original = _build_docx(tmp_path / "original.docx")
    copy = _build_docx(tmp_path / "copy.docx")
    registration_path = tmp_path / "registration.json"
    registration_path.write_text(
        json.dumps(
            {
                "material_id": "pilot-paper-001",
                "copy": {"sha256": check.measure(copy).sha256},
                "checklist": {"result": None, "applies_to_sha256": ""},
                "authorisation": {"scope": "pilot/**", "record": "docs/acceptance/x.md"},
                "storage": {"root": "E:/trial-material", "relative_path": "pilot/copy.docx"},
                "metadata": {
                    "page_count": 1,
                    "word_count": 1,
                    "figure_count": 0,
                    "table_count": 0,
                    "comment_count": 0,
                    "revision_mark_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    code, out, _ = _run(
        "--copy",
        str(copy),
        "--original",
        str(original),
        "--registration",
        str(registration_path),
        "--require-signed",
    )
    assert code == 1
    assert "D-6" in out
