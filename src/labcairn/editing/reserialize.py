"""Option B: rewrite the whole part, and let the serialiser re-spell it.

**What this module is for.** Not a candidate for the product — the option the
record had to measure before rejecting it. Parse `word/document.xml`, change
the located run in the tree, then **write the whole part out again**. The
claim this puts a number on is the difference between *"the parts we did not
touch are untouched"* and *"the regions we did not touch are untouched"*. A
part-level rewrite keeps the first and gives up the second, and the second is
what §5.7 item 4 asks to be compared rather than assumed.

**Why the prefixes are registered rather than left to the default.**
`ElementTree` renames an unregistered prefix to ``ns0``, ``ns1`` …, and
Word's ``mc:Ignorable`` and ``mc:Choice Requires`` attributes name prefixes
**by spelling**: ``mc:Ignorable="w14"`` with no ``w14`` declared is a promise
about markup compatibility that points at nothing, which is the shape of a
repair prompt. Rejecting this option for a defect that belongs to a careless
serializer rather than to the option would be a measurement of the wrong
thing, so the declarations are harvested from the source and registered
before the rewrite. What the report then prints is the option's own cost,
and the registered-prefix check is reported beside it so the reader can see
which of the two was tested.

**The global side effect, stated.** :func:`ElementTree.register_namespace`
writes process-global state, and this module calls it. That is one of the
reasons the module exists to be measured and is imported by no product path.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from typing import Final

from labcairn.editing.drafts import ApprovedEdit, package_bytes_with_part, read_part
from labcairn.editing.survey import DOCUMENT_PART, root_open_tag

__all__ = ["registered_prefixes", "reserialize_bytes", "rewrite_whole_part"]

W: Final[str] = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML: Final[str] = "http://www.w3.org/XML/1998/namespace"

#: The ``xmlns:prefix="uri"`` declarations on the source's root element.
_DECLARATION: Final[re.Pattern[str]] = re.compile(r'xmlns:([A-Za-z0-9_]+)="([^"]+)"')


def registered_prefixes(part: bytes) -> dict[str, str]:
    """The prefix-to-URI map the file itself declares.

    **Read off the root element.** An earlier version of this function took
    the bytes up to the first ``>`` in the part, which is the end of the XML
    declaration: it found no prefixes, registered none, and every rewrite
    through this option renamed ``w:`` to ``ns0:`` and left
    ``mc:Choice Requires="wps"`` naming a prefix the file no longer declared.
    The ``ignorables_missing`` column then reported that as the option's cost.
    It was the probe's cost. The declaration scan is shared with the survey
    now, so both the survey and this option read the same tag.
    """
    return dict(_DECLARATION.findall(root_open_tag(part)))


def rewrite_whole_part(original_part: bytes, new_text: str, old_text: str) -> bytes:
    """Replace one run's text in the tree and re-serialise the entire part.

    **Located the same way the seam locates it — one plain run, its whole
    text — so the two options differ only in what they write back.** The
    walk is over ``w:p`` in document order, which is the reader's numbering
    and the seam's, and the first plain run carrying exactly ``old_text`` is
    the one that changes.
    """
    prefixes = registered_prefixes(original_part)
    for prefix, uri in prefixes.items():
        ElementTree.register_namespace(prefix, uri)

    root = ElementTree.fromstring(original_part)
    for paragraph in root.iter(f"{{{W}}}p"):
        for run in paragraph.iter(f"{{{W}}}r"):
            nodes = [child for child in run if child.tag == f"{{{W}}}t"]
            if len(nodes) != 1 or (nodes[0].text or "") != old_text:
                continue
            nodes[0].text = new_text
            nodes[0].set(f"{{{XML}}}space", "preserve")
            written = ElementTree.tostring(root, encoding="UTF-8", xml_declaration=True)
            assert isinstance(written, bytes)
            return written
    raise LookupError(f"option B found no run carrying exactly {old_text!r}")


def reserialize_bytes(data: bytes, edit: ApprovedEdit) -> bytes:
    """The whole-part rewrite of one manuscript, for the comparison.

    The package is rebuilt by the same carrier the seam uses, with the same
    entry order and metadata, so what this option shows is its serialiser and
    nothing else — not a different ZIP writer.
    """
    part = read_part(data, DOCUMENT_PART)
    rewritten = rewrite_whole_part(part, edit.new_text, edit.old_text)
    return package_bytes_with_part(data, DOCUMENT_PART, rewritten)
