"""The edit seam: what `LC-P3-02` measured about editing an existing manuscript.

**What this package is.** The Phase 3 G1 experiment's own modules. Execution
plan §6 states the gap they close: *"No proved fidelity-preserving edit to an
existing manuscript, no marked-draft and clean-draft export from that edit,
and no Word open/reopen matrix."* The read side already exists
(:mod:`labcairn.material.ooxml`); the report-only writer already exists
(:mod:`labcairn.reports.render.docx`); nothing between them had proved that a
change can be written **into** a manuscript whose parts the product did not
author.

**What it is not.** Not the integrated revision loop. No project-scoped import
receipt, no read-only-original guard, no publication receipt — that is
`LC-P3-03`. No proposal-to-approved-edit-to-response-table binding and no
quality report — that is `LC-P3-04`. Nothing here is wired into a task, an
operation, or the product's write seam
(:mod:`labcairn.workspace.outputs`), and the functions return **bytes**
rather than landing a file, so the seam stays the only place the product
writes. `ADR-0021` records the two dependencies this package has to §7's
path-length budget and to `LC-P3-03`'s independent copy, and records the copy
this experiment uses as **temporary**, because an experiment's shortcut that
is not labelled is how a temporary thing becomes a product mechanism.

**The modules, and the one question each answers.**

``survey``      — what does this package carry, and where does the located
                  passage sit inside it?
``drafts``      — the surgical option: locate one element's bytes, replace
                  them, carry every other byte forward.
``reserialize`` — what re-serialising the whole part costs.
``library``     — what the declared library's own write costs.
``rebuild``     — what writing a new document from the read text costs.
``fidelity``    — the comparison that turns the four answers above into numbers.
``samples``     — the substitute set they are measured on, synthetic and public.

The decision is in ``docs/adr/ADR-0021-manuscript-editing-rewrite.md``, the
matrix in ``docs/acceptance/LC-P3-02-support-matrix.md``, and the run in
``docs/acceptance/LC-P3-02-substitute-run-2026-11-08.md``.
"""
