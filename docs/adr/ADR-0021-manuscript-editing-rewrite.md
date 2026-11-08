# ADR-0021 — Manuscript editing: a surgical run splice on a temporary copy

**Date:** 2026-11-08. **Head:** `9765527ba16c2bfdafc61d32ce78616d2aa2deb1`.
**Status:** proposed. The independent copy is **temporary**, and the adoption
is provisional until the real-sample run and the human reopen checklist exist.

## Context and concrete problem

`LC-P3-02` asks whether the product can edit an existing DOCX manuscript
without damaging the parts it did not target, and for which hosts and
structures. The read side already exists (`ooxml.py`, `revisions.py`,
`alignment.py`); the write side is a report-only python-docx writer. The
experiment uses synthetic manuscripts covering comments, tracked revisions,
tables, equations, images, fields, text boxes, content controls, hyperlinks
and media, and compares four rewrite strategies over marked and clean forms.
The trial hosts are WPS Office 12.1.0.29690 (primary) and Microsoft Office 2010
(compatibility reference); COM and ProgID automation are not allowed, so the
host open/reopen half is a human checklist.

## Alternatives

- **surgical** — locate the one run and splice the text; 76 of 76 class rows
  stayed identical, 66 of 66 region rows stayed identical, declaration and
  entry order were kept, and the marked draft carried the change. One reopen
  problem remains: `docx_nested_revision`.
- **reserialize** — 68 of 68 class rows identical but 22 region rows respelled,
  declaration dropped, `w14` ignorable missing; the marked draft did not carry
  the change.
- **library** — 68 of 68 class rows identical and 66 of 66 region rows
  identical, but declaration and entry order were not kept and the marked
  draft did not carry the change; six parts changed.
- **rebuild** — 52 of 68 class rows changed or missing and all region rows
  changed or missing; 19 parts changed; the marked draft did not carry the
  change.

## Decision

Adopt the **surgical** option for the substitute set. It is the only option
that both preserves the untargeted regions and carries the marked draft, and
its remaining problem is a named reopen issue rather than an unmeasured
region. The independent copy is **temporary**: the adoption is provisional
until the real advisor sample is supplied and the WPS/Office human checklist
is performed. The integrated loop remains `LC-P3-03`, and the write-seam
path-length repair remains this batch's §7 dependency; neither is claimed by
this ADR.

## Risks

- The corpus is synthetic; a host's answer about a synthetic file is not a
  host's answer about a real manuscript. The human checklist is **NOT RUN**.
- The real advisor sample is held open pending the owner; no synthetic result
  substitutes for it.
- The surgical option still reports `docx_nested_revision` on reopen; it is
  recorded as an open problem, not a pass.
- COM/ProgID automation is not allowed; the host half must remain manual.
- The 260-character path wall and the §7 write-seam repair sequence against
  this ticket; no option removes that dependency.
