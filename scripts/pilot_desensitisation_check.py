"""Measure the desensitisation checklist's items against a copy and its original.

**What this is for.** The checklist
(``docs/plans/LC-P4-PILOT-desensitisation-checklist.md``) is written for a
person to work top to bottom: open the copy, read the properties panel,
count the comments, look at the markup.  Every one of those readings is a
number somebody has to type, and a number somebody types is a number that
can be wrong.

This tool computes the readings a machine can compute -- the counts, the
digests, the equality between the copy and the original -- and prints the
checklist's items with those readings attached.  What a machine cannot
decide it leaves ``undecided``: whether a string carries a person's name,
whether an affiliation sentence names a unit, whether an annotation's anchor
is the right one.  Those stay the owner's, and the tool says so on each
item rather than quietly passing it.

**What it never prints.** The manuscript's text, a property's value, a
comment's body, a revision's text.  The output is counts, booleans and
digests.  The facts a human needs to decide the undecided items are given
in the shape that does not carry the material: "four built-in properties are
non-empty and are not the pseudonym", never the values.

**What it decides.** A verdict is ``pass`` only where a fact and the
checklist's own requirement meet directly, ``fail`` only where they miss
directly, and ``undecided`` everywhere else.  The tool has no heuristic
that turns into a pass: a pattern search that finds no project number is
reported as "no pattern hit", which is a fact about the search, not a
verdict on the item.

Usage::

    python scripts/pilot_desensitisation_check.py \\
        --copy <path> --original <path> [--outline <path>] \\
        [--pseudonym NAME] [--json OUT.json]

The ``--outline`` argument is the heading outline exported from the copy (the
same file the registration tool hashes); without it item B-3 is decided from
the copy alone, which cannot compare two outlines.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

TOOL_VERSION = 1

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DC = "{http://purl.org/dc/elements/1.1/}"
CP = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"
EP = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"

#: The revision kinds the checklist's item B-2 counts.  ``ins`` and ``del``
#: are the trail the pilot's trajectory view reads; the ``*Change`` kinds are
#: the format changes, which the checklist counts alongside them.
REVISION_KINDS: tuple[str, ...] = (
    "ins",
    "del",
    "moveFrom",
    "moveTo",
    "pPrChange",
    "rPrChange",
    "sectPrChange",
    "tblPrChange",
    "trPrChange",
    "tcPrChange",
    "numberingChange",
    "cellIns",
    "cellDel",
    "cellMerge",
)

#: The built-in properties the checklist's items A-1 and A-6 name.
BUILTIN_PROPERTIES: tuple[str, ...] = (
    "creator",
    "lastModifiedBy",
    "title",
    "subject",
    "keywords",
    "description",
    "category",
    "company",
    "manager",
)

#: The role labels a revision's or a comment's author field may carry.  The
#: checklist's item C-2 gives two examples and says "e.g.", so the set is
#: the tool's default and the caller may pass another.
DEFAULT_ROLE_LABELS: tuple[str, ...] = ("advisor", "student-1", "student-2", "author", "editor")

#: An address-shaped string in the visible text.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

#: A project-number-shaped string in the visible text.  The search is a
#: search: a miss is reported as a miss, never as a verdict.
PROJECT_NUMBER = re.compile(
    r"(?:\u9879\u76ee(?:\u7f16\u53f7|\u53f7)|\u8bfe\u9898(?:\u7f16\u53f7|\u53f7)|\u57fa\u91d1(?:\u7f16\u53f7|\u53f7)|grant\s*(?:no\.?|number)|"
    r"contract\s*(?:no\.?|number)|NSFC|CFCN|No\.\s*[A-Za-z]{1,4}\d{4,})",
    re.IGNORECASE,
)

#: The role-label shape a pseudonym takes: a short label, not a sentence.
PSEUDONYM = re.compile(r"^[A-Za-z][A-Za-z0-9 ._-]{0,39}$")


class CheckError(Exception):
    """A refusal to measure, with the reason in English."""


@dataclass(frozen=True)
class Measurement:
    """What one document carries, read from its own parts."""

    sha256: str
    byte_size: int
    file_name: str
    properties: dict[str, str]
    custom_property_names: tuple[str, ...]
    revision_counts: dict[str, int]
    revision_authors: tuple[str, ...]
    revision_text_chars: int
    comment_count: int
    comment_authors: tuple[str, ...]
    comment_text_chars: int
    comment_anchored: int
    outline: tuple[str, ...]
    visible_text: str
    header_footer_text: str
    header_footer_hits: int
    paragraph_count: int


@dataclass(frozen=True)
class Item:
    """One checklist item, its reading and its verdict."""

    item: str
    title: str
    verdict: str
    facts: dict[str, Any] = field(default_factory=dict)
    human: str = ""


def _read_part(path: Path, name: str) -> bytes | None:
    try:
        with zipfile.ZipFile(path) as archive:
            try:
                return archive.read(name)
            except KeyError:
                return None
    except zipfile.BadZipFile as error:
        raise CheckError(f"{path} is not a readable zip archive") from error


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_of(node: ElementTree.Element) -> str:
    return "".join(element.text or "" for element in node.iter(f"{W}t"))


def _core_properties(core: bytes) -> dict[str, str]:
    root = ElementTree.fromstring(core)
    values: dict[str, str] = {}
    for tag in ("creator", "title", "subject", "description"):
        node = root.find(DC + tag)
        values[tag] = (node.text or "").strip() if node is not None else ""
    for tag in ("lastModifiedBy", "keywords", "category"):
        node = root.find(CP + tag)
        values[tag] = (node.text or "").strip() if node is not None else ""
    return values


def _app_properties(app: bytes) -> dict[str, str]:
    root = ElementTree.fromstring(app)
    values: dict[str, str] = {}
    for tag in ("Company", "Manager"):
        node = root.find(EP + tag)
        values[tag] = (node.text or "").strip() if node is not None else ""
    return values


def _outline_styles(styles: bytes | None) -> set[str]:
    """The style ids that carry a document outline level.

    The level is read from the style's own ``outlineLvl`` rather than from
    its name, so a document whose headings are named in the document's own
    language is read the same way as one named in English.
    """
    if styles is None:
        return set()
    root = ElementTree.fromstring(styles)
    outline_styles: set[str] = set()
    for style in root.iter(f"{W}style"):
        style_id = style.get(f"{W}styleId", "")
        level = style.find(f"{W}pPr/{W}outlineLvl")
        if style_id and level is not None:
            outline_styles.add(style_id)
    return outline_styles


def _visible_text(document: bytes) -> str:
    """The final view: inserted text kept, deleted text dropped."""
    root = ElementTree.fromstring(document)
    chunks: list[str] = []
    for paragraph in root.iter(f"{W}p"):
        for node in paragraph.iter():
            if node.tag == f"{W}t":
                chunks.append(node.text or "")
            elif node.tag == f"{W}tab":
                chunks.append("\t")
        chunks.append("\n")
    return "".join(chunks)


def _header_footer_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [
            name for name in archive.namelist() if re.match(r"word/(header|footer)\d*\.xml$", name)
        ]
        chunks: list[str] = []
        for name in names:
            try:
                root = ElementTree.fromstring(archive.read(name))
            except (KeyError, ElementTree.ParseError):
                continue
            chunks.append(_text_of(root))
    return "\n".join(chunks)


def measure(path: Path) -> Measurement:
    """Read one document's own parts into the readings the items compare."""
    if not path.is_file():
        raise CheckError(f"{path} is not a file")

    core = _read_part(path, "docProps/core.xml")
    app = _read_part(path, "docProps/app.xml")
    custom = _read_part(path, "docProps/custom.xml")
    document = _read_part(path, "word/document.xml")
    styles = _read_part(path, "word/styles.xml")
    comments = _read_part(path, "word/comments.xml")

    properties: dict[str, str] = {}
    if core is not None:
        properties.update(_core_properties(core))
    if app is not None:
        properties.update(_app_properties(app))
    for name in BUILTIN_PROPERTIES:
        properties.setdefault(name, "")

    custom_names: tuple[str, ...] = ()
    if custom is not None:
        root = ElementTree.fromstring(custom)
        custom_names = tuple(node.get("name", "") for node in root if node.get("name") is not None)

    revision_counts: dict[str, int] = dict.fromkeys(REVISION_KINDS, 0)
    revision_authors: set[str] = set()
    revision_text = 0
    paragraph_count = 0
    outline: list[str] = []
    visible = ""
    if document is not None:
        root = ElementTree.fromstring(document)
        outline_styles = _outline_styles(styles)
        for kind in REVISION_KINDS:
            for node in root.iter(f"{W}{kind}"):
                revision_counts[kind] += 1
                author = node.get(f"{W}author")
                if author is not None:
                    revision_authors.add(author)
                revision_text += len(_text_of(node))
        for paragraph in root.iter(f"{W}p"):
            paragraph_count += 1
            style_node = paragraph.find(f"{W}pPr/{W}pStyle")
            if style_node is not None and style_node.get(f"{W}val", "") in outline_styles:
                outline.append(_text_of(paragraph).strip())
        visible = _visible_text(document)

    comment_count = 0
    comment_authors: set[str] = set()
    comment_text = 0
    comment_anchored = 0
    if comments is not None:
        root = ElementTree.fromstring(comments)
        anchored = _comment_anchors(document)
        for node in root.iter(f"{W}comment"):
            comment_count += 1
            author = node.get(f"{W}author")
            if author is not None:
                comment_authors.add(author)
            comment_text += len(_text_of(node))
            comment_id = node.get(f"{W}id", "")
            if comment_id in anchored:
                comment_anchored += 1

    header_footer_text = _header_footer_text(path)
    return Measurement(
        sha256=_digest(path),
        byte_size=path.stat().st_size,
        file_name=path.name,
        properties=properties,
        custom_property_names=custom_names,
        revision_counts=revision_counts,
        revision_authors=tuple(sorted(revision_authors)),
        revision_text_chars=revision_text,
        comment_count=comment_count,
        comment_authors=tuple(sorted(comment_authors)),
        comment_text_chars=comment_text,
        comment_anchored=comment_anchored,
        outline=tuple(outline),
        visible_text=visible,
        header_footer_text=header_footer_text,
        header_footer_hits=_part_count(path),
        paragraph_count=paragraph_count,
    )


def _part_count(path: Path) -> int:
    """How many header and footer parts the document carries."""
    with zipfile.ZipFile(path) as archive:
        return len(
            [
                name
                for name in archive.namelist()
                if re.match(r"word/(header|footer)\d*\.xml$", name)
            ]
        )


def _comment_anchors(document: bytes | None) -> set[str]:
    if document is None:
        return set()
    root = ElementTree.fromstring(document)
    return {
        node.get(f"{W}id", "")
        for node in root.iter(f"{W}commentRangeStart")
        if node.get(f"{W}id", "")
    }


def _property_state(value: str, pseudonym: str | None) -> str:
    """``empty``, ``pseudonym`` or ``non-empty``: a state, never the value."""
    if not value.strip():
        return "empty"
    if pseudonym is not None and value == pseudonym:
        return "pseudonym"
    return "non-empty"


def judge(
    original: Measurement,
    copy: Measurement,
    *,
    pseudonym: str | None = None,
    role_labels: tuple[str, ...] = DEFAULT_ROLE_LABELS,
    outline: tuple[str, ...] | None = None,
    original_outline: tuple[str, ...] | None = None,
    material_id: str | None = None,
    registration: dict[str, Any] | None = None,
) -> list[Item]:
    """Turn two measurements into the checklist's items and their verdicts."""
    items: list[Item] = []
    states = {
        name: _property_state(copy.properties.get(name, ""), pseudonym)
        for name in BUILTIN_PROPERTIES
    }
    non_empty = sorted(name for name, state in states.items() if state == "non-empty")
    blanked = sorted(name for name, state in states.items() if state == "empty")

    creator_state = states["creator"]
    modifier_state = states["lastModifiedBy"]
    items.append(
        Item(
            item="A-1",
            title="Author names",
            verdict=_combine(
                [
                    _property_verdict(states["creator"]),
                    _property_verdict(states["lastModifiedBy"]),
                    "undecided",
                ]
            ),
            facts={
                "author_property_state": creator_state,
                "last_modified_by_property_state": modifier_state,
                "visible_text_byline": "undecided",
            },
            human=(
                "the byline, the footnotes and the title block are read by a person; "
                "the tool does not search the visible text for a name"
            ),
        )
    )

    email_hits = len(EMAIL.findall(copy.visible_text))
    original_emails = len(EMAIL.findall(original.visible_text))
    items.append(
        Item(
            item="A-2",
            title="Affiliations and addresses",
            verdict=_combine(["pass" if email_hits == 0 else "fail", "undecided"]),
            facts={
                "address_shaped_hits_in_copy": email_hits,
                "address_shaped_hits_in_original": original_emails,
                "affiliation_sentences": "undecided",
            },
            human="the affiliation and department strings are read by a person",
        )
    )

    project_hits = len(PROJECT_NUMBER.findall(copy.visible_text))
    items.append(
        Item(
            item="A-3",
            title="Project and funding identifiers",
            verdict="undecided",
            facts={
                "project_number_shaped_hits_in_copy": project_hits,
                "project_number_shaped_hits_in_original": len(
                    PROJECT_NUMBER.findall(original.visible_text)
                ),
                "note": "a pattern search; a miss is a miss, not a verdict",
            },
            human="the identifier's own wording is read by a person",
        )
    )

    items.append(
        Item(
            item="A-4",
            title="Table and figure numbering",
            verdict="undecided",
            facts={
                "paragraph_count_copy": copy.paragraph_count,
                "paragraph_count_original": original.paragraph_count,
            },
            human="the numbering's continuity is read by a person",
        )
    )

    header_footer_text = copy.header_footer_text
    header_hit = any(
        value and value in header_footer_text
        for value in (
            original.properties.get("creator", ""),
            original.properties.get("lastModifiedBy", ""),
        )
    )
    if copy.header_footer_hits == 0:
        header_verdict = "pass"
    elif header_hit:
        header_verdict = "fail"
    else:
        header_verdict = "undecided"
    items.append(
        Item(
            item="A-5",
            title="Headers and footers",
            verdict=header_verdict,
            facts={
                "header_footer_parts": copy.header_footer_hits,
                "original_identity_value_found_in_header_or_footer": header_hit,
            },
            human="a header may name a person in a form the tool cannot read",
        )
    )

    unchanged = sorted(
        name
        for name in BUILTIN_PROPERTIES
        if copy.properties.get(name, "")
        and copy.properties.get(name, "") == original.properties.get(name, "")
    )
    items.append(
        Item(
            item="A-6",
            title="Contact and identity metadata",
            verdict=_combine(["fail" if unchanged else "pass", "undecided", "undecided"]),
            facts={
                "built_in_properties_blanked": blanked,
                "built_in_properties_non_empty": non_empty,
                "built_in_properties_unchanged_from_the_original": unchanged,
                "custom_property_count": len(copy.custom_property_names),
                "custom_property_names": list(copy.custom_property_names),
                "custom_property_names_unchanged_from_the_original": (
                    list(copy.custom_property_names) == list(original.custom_property_names)
                ),
                "revision_author_names": len(copy.revision_authors),
                "comment_author_names": len(copy.comment_authors),
                "comment_author_names_replaced": _authors_replaced(
                    copy.comment_authors, role_labels
                ),
                "revision_author_names_replaced": _authors_replaced(
                    copy.revision_authors, role_labels
                ),
            },
            human=(
                "whether a non-empty property carries a person or a project is read "
                "by a person; the tool reports which properties are non-empty and "
                "which author fields are still the original's"
            ),
        )
    )

    file_ok = material_id is None or copy.file_name.startswith(f"{material_id}.")
    items.append(
        Item(
            item="A-7",
            title="Embedded identifiers",
            verdict="pass" if file_ok else "fail",
            facts={
                "file_name_carries_the_material_id": file_ok,
                "image_metadata": "undecided",
            },
            human="an embedded image's own metadata is stripped by the tooling, not by this tool",
        )
    )

    same_comments = original.comment_count == copy.comment_count
    items.append(
        Item(
            item="B-1",
            title="Advisor annotations",
            verdict="pass" if same_comments else "fail",
            facts={
                "comment_count_original": original.comment_count,
                "comment_count_copy": copy.comment_count,
                "anchored_comments_in_copy": copy.comment_anchored,
                "spot_check_of_three_anchors": "undecided",
            },
            human="the spot-check of three anchors is read by a person",
        )
    )

    revision_equal = original.revision_counts == copy.revision_counts
    items.append(
        Item(
            item="B-2",
            title="Revision marks",
            verdict="pass" if revision_equal else "fail",
            facts={
                "insertions_original": original.revision_counts["ins"],
                "insertions_copy": copy.revision_counts["ins"],
                "deletions_original": original.revision_counts["del"],
                "deletions_copy": copy.revision_counts["del"],
                "format_changes_original": sum(
                    count
                    for kind, count in original.revision_counts.items()
                    if kind.endswith("Change")
                ),
                "format_changes_copy": sum(
                    count for kind, count in copy.revision_counts.items() if kind.endswith("Change")
                ),
                "revision_text_characters_copy": copy.revision_text_chars,
            },
            human="",
        )
    )

    visible_identical = original.visible_text == copy.visible_text
    if outline is not None and original_outline is not None:
        b3_verdict = "pass" if outline == original_outline else "fail"
        b3_facts: dict[str, Any] = {
            "compared": "the two exported outlines",
            "exported_outline_matches_the_original": outline == original_outline,
            "exported_outline_heading_count": len(outline),
        }
    elif copy.outline:
        b3_verdict = "pass" if outline is None or outline == copy.outline else "fail"
        b3_facts = {
            "compared": "the exported outline and the copy's own headings",
            "exported_outline_matches_the_copy": outline is None or outline == copy.outline,
            "heading_count_copy": len(copy.outline),
            "heading_count_original": len(original.outline),
        }
    elif visible_identical:
        b3_verdict = "pass"
        b3_facts = {
            "compared": "the two visible texts",
            "visible_text_identical": True,
            "heading_count_copy": len(copy.outline),
            "heading_count_original": len(original.outline),
        }
    else:
        b3_verdict = "undecided"
        b3_facts = {
            "compared": "nothing",
            "visible_text_identical": False,
            "heading_count_copy": len(copy.outline),
            "heading_count_original": len(original.outline),
        }
    b3_facts["the_copy_carries_heading_styles"] = bool(copy.outline)
    # The size of each visible text, so a record that quotes it can name the
    # reading that produced it rather than carrying the number alone.
    b3_facts["visible_text_characters_copy"] = len(copy.visible_text)
    b3_facts["visible_text_characters_original"] = len(original.visible_text)
    items.append(
        Item(
            item="B-3",
            title="Heading outline",
            verdict=b3_verdict,
            facts=b3_facts,
            human=""
            if b3_verdict != "undecided"
            else "the copy carries no heading styles to compare, and the two texts differ",
        )
    )

    items.append(
        Item(
            item="B-4",
            title="Revision positions",
            verdict="undecided",
            facts={
                "revision_marks_present_in_copy": copy.revision_counts["ins"]
                + copy.revision_counts["del"]
                > 0,
            },
            human="the position of each mark in the document is read by a person",
        )
    )

    items.append(
        Item(
            item="C-1",
            title="Comment text is readable",
            verdict="pass" if copy.comment_text_chars > 0 or copy.comment_count == 0 else "fail",
            facts={
                "comment_count_copy": copy.comment_count,
                "comment_text_characters_copy": copy.comment_text_chars,
            },
            human="",
        )
    )

    items.append(
        Item(
            item="C-2",
            title="Markup authors are role labels",
            verdict="pass"
            if _authors_replaced(copy.revision_authors, role_labels)
            and _authors_replaced(copy.comment_authors, role_labels)
            else "fail",
            facts={
                "revision_author_names": len(copy.revision_authors),
                "comment_author_names": len(copy.comment_authors),
                "all_authors_are_role_labels": _authors_replaced(copy.revision_authors, role_labels)
                and _authors_replaced(copy.comment_authors, role_labels),
            },
            human="",
        )
    )

    items.append(
        Item(
            item="C-3",
            title="Revision text is readable",
            verdict=_combine(
                [
                    "undecided"
                    if copy.revision_counts["ins"] == 0 and copy.revision_counts["del"] == 0
                    else ("pass" if copy.revision_text_chars > 0 else "fail")
                ]
            ),
            facts={
                "revision_text_characters_copy": copy.revision_text_chars,
                "insertions_copy": copy.revision_counts["ins"],
                "deletions_copy": copy.revision_counts["del"],
            },
            human=""
            if copy.revision_counts["ins"] or copy.revision_counts["del"]
            else ("the copy carries no inserted or deleted text to read"),
        )
    )

    anchored_all = copy.comment_anchored == copy.comment_count
    items.append(
        Item(
            item="C-4",
            title="Comment anchors are intact",
            verdict="pass" if anchored_all else "fail",
            facts={
                "comment_count_copy": copy.comment_count,
                "anchored_comments_in_copy": copy.comment_anchored,
            },
            human="",
        )
    )

    items.append(_d_item("D-1", "Material id", material_id, registration))
    items.append(_d_item("D-2", "The authorisation", None, registration))
    items.append(_d_item("D-3", "Metadata", None, registration))
    items.append(_d_item("D-4", "Fingerprint", None, registration, copy=copy))
    items.append(_d_item("D-5", "Storage", None, registration))
    checklist = registration.get("checklist", {}) if registration else {}
    result = checklist.get("result") if isinstance(checklist, dict) else None
    applies_to = str(checklist.get("applies_to_sha256", "")) if isinstance(checklist, dict) else ""
    signed = bool(result)
    applies = bool(applies_to) and applies_to == copy.sha256
    items.append(
        Item(
            item="D-6",
            title="The checklist result",
            verdict="pass" if signed and applies else "undecided",
            facts={
                "signed": signed,
                "result_applies_to_this_copy": applies,
                "result_applies_to_sha256": applies_to,
            },
            human="the owner's signature is what fills it",
        )
    )
    return items


def _property_verdict(state: str) -> str:
    """A built-in property's own verdict: blanked or pseudonymed passes."""
    return "fail" if state == "non-empty" else "pass"


def _combine(verdicts: list[str]) -> str:
    """The whole item's verdict from its parts' verdicts.

    A part that misses is the item's miss; a part nobody has read yet keeps
    the item open.  Nothing turns an unread part into a pass.
    """
    if "fail" in verdicts:
        return "fail"
    if "undecided" in verdicts:
        return "undecided"
    return "pass"


def _authors_replaced(authors: tuple[str, ...], role_labels: tuple[str, ...]) -> bool:
    return all(author in role_labels for author in authors)


def _d_item(
    item: str,
    title: str,
    material_id: str | None,
    registration: dict[str, Any] | None,
    *,
    copy: Measurement | None = None,
) -> Item:
    """A registration item: what the record says, measured against the copy."""
    if registration is None:
        return Item(
            item=item,
            title=title,
            verdict="undecided",
            facts={"registration_read": False},
            human="the registration record was not given to the tool",
        )
    checklist = registration.get("checklist", {})
    facts: dict[str, Any] = {
        "registration_read": True,
        "material_id": registration.get("material_id", ""),
    }

    if item == "D-1":
        recorded = str(registration.get("material_id", ""))
        matches = bool(recorded) and (material_id is None or recorded == material_id)
        facts["material_id_matches"] = matches
        return Item(
            item=item,
            title=title,
            verdict="pass" if matches else "fail",
            facts=facts,
            human="",
        )

    if item == "D-2":
        authorisation = registration.get("authorisation", {})
        scope = str(authorisation.get("scope", ""))
        relative = str(registration.get("storage", {}).get("relative_path", ""))
        covers = bool(scope) and bool(relative) and _scope_covers(scope, relative)
        grant_record = str(authorisation.get("record", ""))
        facts["scope_covers_the_copy"] = covers
        facts["grant_record_named"] = bool(grant_record)
        return Item(
            item=item,
            title=title,
            verdict="pass" if covers and grant_record else "fail",
            facts=facts,
            human="",
        )

    if item == "D-3":
        metadata = registration.get("metadata", {})
        wanted = (
            "page_count",
            "word_count",
            "figure_count",
            "table_count",
            "comment_count",
            "revision_mark_count",
        )
        present = [key for key in wanted if isinstance(metadata.get(key), int)]
        facts["metadata_fields_present"] = len(present)
        facts["metadata_fields_expected"] = len(wanted)
        return Item(
            item=item,
            title=title,
            verdict="pass" if len(present) == len(wanted) else "fail",
            facts=facts,
            human="",
        )

    if item == "D-4" and copy is not None:
        recorded = str(registration.get("copy", {}).get("sha256", ""))
        matches = recorded == copy.sha256
        facts["recorded_sha256"] = recorded
        facts["copy_sha256_matches_the_record"] = matches
        facts["applies_to_sha256"] = checklist.get("applies_to_sha256", "")
        return Item(
            item=item,
            title=title,
            verdict="pass" if matches else "fail",
            facts=facts,
            human="",
        )

    if item == "D-5":
        storage = registration.get("storage", {})
        root = str(storage.get("root", ""))
        relative = str(storage.get("relative_path", ""))
        facts["storage_root_named"] = bool(root)
        facts["relative_path_under_the_root"] = bool(root) and bool(relative)
        return Item(
            item=item,
            title=title,
            verdict="pass" if root and relative else "fail",
            facts=facts,
            human="",
        )

    verdict = "pass" if registration.get("material_id") else "fail"
    return Item(item=item, title=title, verdict=verdict, facts=facts, human="")


def _scope_covers(scope: str, relative: str) -> bool:
    """Whether a grant's scope covers a path, on the scope's own terms."""
    normalised = relative.replace("\\", "/").lstrip("/")
    pattern = scope.replace("\\", "/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return normalised == prefix or normalised.startswith(prefix + "/")
    return fnmatch.fnmatchcase(normalised, pattern)


def _read_outline(path: Path | None) -> tuple[str, ...] | None:
    if path is None:
        return None
    if not path.is_file():
        raise CheckError(f"{path} is not a file")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return tuple(line for line in lines if line)


def build_report(
    original: Measurement,
    copy: Measurement,
    items: list[Item],
    *,
    material_id: str | None,
    registration: dict[str, Any] | None,
) -> dict[str, Any]:
    """The report as a dictionary: readings and verdicts, never material."""
    return {
        "tool": "pilot-desensitisation-check",
        "tool_version": TOOL_VERSION,
        "material_id": material_id or "",
        "original": {"sha256": original.sha256, "byte_size": original.byte_size},
        "copy": {"sha256": copy.sha256, "byte_size": copy.byte_size},
        "registration_read": registration is not None,
        "items": [
            {
                "item": item.item,
                "title": item.title,
                "verdict": item.verdict,
                "facts": item.facts,
                "needs_a_person": item.human,
            }
            for item in items
        ],
    }


def render(report: dict[str, Any]) -> str:
    """The report as text: one line per item, then the counts."""
    lines: list[str] = []
    for entry in report["items"]:
        facts = ", ".join(
            f"{key}={value}" for key, value in entry["facts"].items() if value != "undecided"
        )
        lines.append(f"{entry['item']:<4} {entry['verdict']:<11} {entry['title']}")
        if facts:
            lines.append(f"      {facts}")
        if entry["needs_a_person"]:
            lines.append(f"      needs a person: {entry['needs_a_person']}")
    counts: dict[str, int] = {}
    for entry in report["items"]:
        counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
    lines.append("")
    lines.append(
        "verdicts: " + ", ".join(f"{verdict}={count}" for verdict, count in sorted(counts.items()))
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pilot_desensitisation_check",
        description=(
            "Measure the desensitisation checklist's items against a copy and its original."
        ),
    )
    parser.add_argument("--copy", required=True, help="the desensitised copy")
    parser.add_argument("--original", required=True, help="the original the copy was derived from")
    parser.add_argument(
        "--outline", default=None, help="the heading outline exported from the copy"
    )
    parser.add_argument(
        "--original-outline",
        default=None,
        help="the heading outline exported from the original",
    )
    parser.add_argument(
        "--pseudonym",
        default=None,
        help="the fixed pseudonym the copy's author fields may carry",
    )
    parser.add_argument(
        "--material-id",
        default=None,
        help="the pilot's material id, for the copy's file name",
    )
    parser.add_argument(
        "--registration",
        default=None,
        help="the registration record to read D-1..D-6 from",
    )
    parser.add_argument("--json", default=None, help="where to write the report as JSON")
    parser.add_argument(
        "--require-signed",
        action="store_true",
        help="fail unless item D-6 is signed for this copy",
    )
    arguments = parser.parse_args(argv)

    if arguments.pseudonym is not None and not PSEUDONYM.match(arguments.pseudonym):
        print("the pseudonym is not a label the record can hold")
        return 2

    registration: dict[str, Any] | None = None
    if arguments.registration is not None:
        registration_path = Path(arguments.registration)
        if not registration_path.is_file():
            print(f"{registration_path} is not a file")
            return 2
        try:
            loaded = json.loads(registration_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            print(f"{registration_path} is not readable JSON: {error}")
            return 2
        registration = loaded if isinstance(loaded, dict) else None

    try:
        original = measure(Path(arguments.original))
        copy = measure(Path(arguments.copy))
        outline = _read_outline(Path(arguments.outline) if arguments.outline else None)
        original_outline = _read_outline(
            Path(arguments.original_outline) if arguments.original_outline else None
        )
    except CheckError as error:
        print(str(error))
        return 2

    items = judge(
        original,
        copy,
        pseudonym=arguments.pseudonym,
        outline=outline,
        original_outline=original_outline,
        material_id=arguments.material_id,
        registration=registration,
    )
    report = build_report(
        original,
        copy,
        items,
        material_id=arguments.material_id,
        registration=registration,
    )
    print(render(report))
    if arguments.json is not None:
        Path(arguments.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {arguments.json}")
    if arguments.require_signed:
        d6 = next((entry for entry in report["items"] if entry["item"] == "D-6"), None)
        if d6 is None or d6["verdict"] != "pass":
            print("item D-6 is not signed for this copy")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
