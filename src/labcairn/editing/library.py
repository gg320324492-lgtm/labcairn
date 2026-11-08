"""Option C: hand the manuscript to the declared library and take back what it writes.

**What this module is for.** `ADR-0013` chose python-docx for the report form,
and the gap register names the report-only writer as the library boundary this
ticket is measured against. The question here is not whether python-docx is a
good report writer — that was decided, and the report writer still is one —
but what its **own** write costs when the document it saves is somebody
else's manuscript rather than a document the library authored.

**Why it is measured and not argued.** The library's model is a document: it
parses the parts it knows and `save` writes the package back through its own
OPC layer. Whether a part the library has no class for travels as a blob or
disappears, whether the entry order and the ZIP metadata survive, whether
``mc:Ignorable`` keeps its prefixes, whether its paragraph numbering agrees
with the reader's — those are facts about a version of a library, and a
version of a library is the kind of value this project re-measures rather than
carries forward.

**Nothing here is proposed as the product's edit path.** This module exists so
:func:`labcairn.editing.fidelity.run_arm` can set its numbers beside the
surgical option's, and so the support matrix can name which option the record
adopted and at what measured cost the others were rejected. The library is
imported **inside** the functions, for `ADR-0013`'s constraint 2: a task that
never asks for this arm must not pay for lxml.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from docx.document import Document as DocumentType

__all__ = ["LIBRARY", "library_bytes", "library_edit_bytes", "library_paragraph_count"]

#: The library this option goes through. Its version is reported with every
#: number made through it, because a different version is a different answer.
LIBRARY: Final[str] = "python-docx"

#: The text element, in the form lxml spells it. **Not** ``"w:t"``: a
#: ``.iter("w:t")`` over python-docx's tree matches nothing at all, because
#: lxml stores the namespace as a URI, and an option whose every edit "found
#: nothing" would be a measurement of the probe rather than of the library.
_W_T: Final[str] = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


def _open(data: bytes) -> DocumentType:
    import docx

    return docx.Document(io.BytesIO(data))


def _save(document: DocumentType) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def library_bytes(data: bytes) -> bytes:
    """The manuscript opened and saved by the library with **no edit at all**.

    This is the container's own cost before any change is contemplated: what a
    round trip through the library does to a file it was only asked to carry.
    Every edit arm is then measured against it, so the report can tell the
    library's rewrite from the edit's rewrite rather than adding the two.
    """
    return _save(_open(data))


def library_paragraph_count(data: bytes) -> int:
    """How many paragraphs the library sees, which is not how many there are.

    **The finding this function exists to make countable.** The library's
    ``paragraphs`` is the body's own paragraphs; a sentence inside a table
    cell, a text box or a content control is not in that list. The reader
    numbers every ``w:p`` in document order, and so does the seam. Two address
    spaces that disagree about which paragraph is number five are not one
    product, and an edit addressed through the library's list would change the
    wrong sentence in a manuscript with a table.
    """
    return len(_open(data).paragraphs)


def library_edit_bytes(data: bytes, old_text: str, new_text: str) -> bytes:
    """The edit applied to the library's tree, then saved through the library.

    **The text node is found through lxml rather than through the paragraph
    list, and that is the measurement.** Going through ``document.paragraphs``
    would silently skip a target inside a table cell and raise a lookup error
    that says more about the library's model than about the rewrite; reaching
    the element directly gives the library its best chance to preserve the
    package, which is what the comparison owes it.
    """
    document = _open(data)
    located = 0
    for element in document.element.body.iter(_W_T):
        if (element.text or "") == old_text:
            element.text = new_text
            located += 1
            break
    if not located:
        raise LookupError(f"the library found no w:t carrying exactly {old_text!r}")
    return _save(document)
