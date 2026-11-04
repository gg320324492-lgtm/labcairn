"""The words a report says in every form it is written in.

A report is exported four times, and the four files are read by four kinds of
reader. What they must not do is say four different things: a reader who
compares the Markdown with the PDF has to be reading one report, not two that
happen to share a title. So the sentences that are **the product's voice**
rather than the report's content live here, once, and every renderer draws
them from this module.

There are three of them, and each earns its place.

**The first-pass notice.** The work order (LC-P1-11) says to *"limit
first-pass report format and explicitly say not journal-ready"*, and a report
that does not say it is claiming a standard it has not met. The limit is not
a property of one format, so it cannot be one format's string.

**The reproducibility notice.** ADR-0013's constraint 11 says the report must
state which of its four forms are reproducible, because one of them is not:
a PDF carries the creation date of the render, and the owner decided on
2026-10-20 that its bytes are recorded but not claimed reproducible. The
DOCX's timestamps are the document's own ``as_of`` rather than the writer's
clock, so it is reproducible too — see
:mod:`labcairn.reports.render.docx`. A report that stayed silent about the
PDF would let a reader assume that comparing two exports by hash means
something it does not.

**The interpretation marker.** ADR-0004's A10 says an interpretation is never
machine-verified, because C4 returned ``not_checked`` and Phase 1 has no
state that could hold a pass. The marker is **imported from the figure's
renderer** rather than written out here, and that is the whole point of the
import: the figure has said "this is an interpretation" in one spelling
since LC-P1-10, and a report that spelled the marker differently would make
a reader wonder whether the two were the same claim. There is one string in
the tree, and it is used by every renderer that marks an interpretation.

The marker is a **product constant and not a model value**: the model says
*which* blocks are interpretations, and the marker says what that means in
words. A renderer that chose its own wording would be deciding, and the
brief's rule is that a renderer draws.
"""

from __future__ import annotations

from typing import Final

from labcairn.analysis.chart import INTERPRETATION_MARKER

__all__ = [
    "FIRST_PASS_NOTICE",
    "INTERPRETATION_MARKER",
    "REPRODUCIBILITY_NOTICE",
]

#: The limit every export states on its own face.
#:
#: First-pass, and explicitly not journal-ready. The work order requires the
#: limit to be stated rather than implied, and a limit that four renderers
#: each phrase in their own words is a limit that four files disagree about.
FIRST_PASS_NOTICE: Final[str] = (
    "This is a first-pass report produced by LabCairn. It is not journal-ready."
)

#: Which of the report's four forms can be compared by hash.
#:
#: The owner decided on 2026-10-20 (the breakdown's §1.4.3, Option A) that
#: the **PDF**'s bytes are recorded but not claimed reproducible, because a
#: PDF's creation date is the moment of the render and pinning it would be a
#: false statement about when the file was made. That reason does not reach
#: the DOCX: its entries are stamped with the report's ``as_of``, which is
#: the date the document itself states, not the writer's clock. So the three
#: text-and-container forms are comparable by hash and the PDF is not. A
#: report that did not say so would let a reader hash two exports and read
#: agreement into a difference that is only the clock.
REPRODUCIBILITY_NOTICE: Final[str] = (
    "The Markdown, HTML and DOCX forms of this report are byte-reproducible; the PDF form is not."
)
