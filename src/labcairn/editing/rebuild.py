"""Option D: write a new document out of what the reader says the manuscript says.

**What this module is for.** It is the shape the project already owns for
DOCX output: `src/labcairn/reports/render/docx.py` builds a **new** package
from a model, and `ADR-0013` chose python-docx to do it. Asked of a
manuscript, the same shape means: take the text back out through
:mod:`labcairn.material.ooxml`, apply the approved change to that text, and
write a document from it. A team under pressure reaches for the writer it has
rather than the writer it needs, so this arm exists to be priced.

**Why the cost is not obvious from the code.** Everything this arm writes is
well-formed. The paragraph text is right, the styles part is there, the file
opens. What is gone is what the arm never read: a reviewer's comments live in
another part, a tracked revision lives in an element the read model reports
but does not carry forward, an equation is ``m:oMath`` and this arm writes
``w:r``, and a figure is a relationship to bytes in ``word/media/`` that no
paragraph mentions. The report prints those as counts, because "the figure is
gone" is a sentence and "images 1 to 0" is a measurement.

**The lazy import, again.** `ADR-0013`'s constraint 2: a run that never asks
for this arm does not pay for lxml.
"""

from __future__ import annotations

import io

from labcairn.editing.drafts import ApprovedEdit, plan_edit
from labcairn.editing.survey import DOCUMENT_PART

__all__ = ["rebuild_bytes"]


def _new_document(texts: list[str]) -> bytes:
    import docx

    document = docx.Document()
    for text in texts:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def rebuild_bytes(data: bytes, edit: ApprovedEdit) -> bytes:
    """A fresh package carrying the manuscript's text, with the edit applied.

    **The text comes from the product's own reader, not from a second
    parser.** This arm is exactly the question "what if the read model were
    also the write model", so it uses the read model: the accepted view,
    paragraph by paragraph, with the located paragraph's text substituted. A
    difference between this arm and the seam is therefore a difference about
    the reader's reach, which is the more interesting thing to measure.

    **The gate runs first.** :func:`labcairn.editing.drafts.plan_edit` is
    called before anything is built, so an edit the seam refuses is refused
    here too and no arm gets to write what the matrix says may not be
    written. An arm that could bypass the gate would make the refusal
    evidence worth nothing.
    """
    from labcairn.material.ooxml import read_document

    plan_edit(data, edit)
    document = read_document(data)
    texts = list(document.paragraphs)
    index = edit.paragraph - 1
    if not 0 <= index < len(texts):
        raise LookupError(f"the rebuild arm has no paragraph {edit.paragraph}")
    current = texts[index]
    if current == edit.old_text:
        texts[index] = edit.new_text
    elif edit.old_text in current:
        # A rebuild arm has no run structure to preserve, so it substitutes
        # inside the paragraph's whole text. Reporting that substitution is
        # the point: the arm changes more than the seam was asked to change.
        texts[index] = current.replace(edit.old_text, edit.new_text, 1)
    else:
        raise LookupError(f"the rebuild arm found nothing to replace in {DOCUMENT_PART}")
    return _new_document(texts)
