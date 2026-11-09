"""The quality report: file delivery and research quality, decided apart.

**What this module is.** One of LC-P3-04's four deliverables, and the one
that answers execution plan §4's *research quality* row: *"Missing
experiments, references or data block a quality pass or become named tasks.
File-delivery status and research-quality status are decided separately."*

**The two statuses are two sections, and neither answers for the other.**
The **file-delivery** section says whether the bytes landed: the marked and
the clean draft are published under receipts, the outputs bind to one task,
one input version and one output version, and the seam's refusals are named
as handovers. The **research-quality** section says whether the *science*
moved: what the opinions asked for, which verdicts the reviewer gave, and —
carried over from the dossier — the explicit unresolved tasks an accepted
change cannot close. A binding whose files all landed can still carry an
unresolved opinion, and **the report says both things without letting
either blur the other**: a quality pass is not claimed because the bytes
landed, and a failed delivery is not read as bad science.

**The report is built from the dossier manifest**, for the same reason the
response table is: the manifest is the binding's own record, and a
caller's summary would be a second spelling of the same facts.

**Every text value is escaped**, the same rule the response table carries:
a comment's text is data and never instructions, and the writer is
LabCairn's own (ADR-0013's boundary).
"""

from __future__ import annotations

from typing import Final

from labcairn.reports.render.markdown import escape_markdown

__all__ = [
    "DELIVERY_SECTION",
    "QUALITY_SECTION",
    "render_quality_report_markdown",
]


#: The two sections' headings. The headings are part of the deliverable:
#: the separation they name is the separation the reader must see.
DELIVERY_SECTION: Final[str] = "File delivery"
QUALITY_SECTION: Final[str] = "Research quality"


def render_quality_report_markdown(manifest_json: str) -> bytes:
    """The quality report, as Markdown bytes, from one dossier manifest.

    :param manifest_json: the dossier manifest's own JSON — the bytes the
        binding wrote, parsed here rather than re-derived.
    :returns: the report, UTF-8. The same manifest gives the same bytes,
        every time: the report is a pure function of the manifest.
    """
    from labcairn.papers.binding import DossierManifest

    manifest = DossierManifest.model_validate_json(manifest_json)

    lines: list[str] = []
    lines.append("# Quality report")
    lines.append("")

    # -- the file-delivery section ------------------------------------- #
    lines.append(f"## {DELIVERY_SECTION}")
    lines.append("")
    lines.append(f"Task: `{escape_markdown(manifest.task_id)}`")
    lines.append(f"Input version: `{escape_markdown(manifest.input_version_id)}`")
    lines.append(f"Output version: `{escape_markdown(manifest.output_version_id)}`")
    lines.append(f"Edge: `{escape_markdown(manifest.edge_id)}`")
    lines.append("")
    lines.append(
        f"Marked draft: receipt `{escape_markdown(manifest.marked_receipt_id)}`, "
        f"sha256 `{escape_markdown(manifest.marked_sha256)}`."
    )
    lines.append(
        f"Clean draft: receipt `{escape_markdown(manifest.clean_receipt_id)}`, "
        f"sha256 `{escape_markdown(manifest.clean_sha256)}`."
    )
    lines.append("")
    delivered = len(manifest.suggestions) - len(manifest.handovers)
    lines.append(
        f"{delivered} of {len(manifest.suggestions)} approved edits were written "
        "through the seam; every refused edit is named below."
    )
    lines.append("")
    if manifest.handovers:
        lines.append("Handed to a person:")
        lines.append("")
        for handover in manifest.handovers:
            lines.append(
                f"- `{escape_markdown(handover.feedback_id)}` — "
                f"{escape_markdown(handover.reason)}: {escape_markdown(handover.detail)} "
                f"{escape_markdown(handover.handover)}"
            )
    else:
        lines.append("Handed to a person: none. The seam applied every approved edit.")
    lines.append("")

    # -- the research-quality section ---------------------------------- #
    lines.append(f"## {QUALITY_SECTION}")
    lines.append("")
    located = sum(1 for o in manifest.opinions if o.location_state == "located")
    uncertain = sum(
        1 for o in manifest.opinions if o.location_state == "uncertain_location"
    )
    lines.append(
        f"{len(manifest.opinions)} opinions were read from the input version: "
        f"{located} located, {uncertain} at an uncertain location."
    )
    lines.append("")
    if manifest.decisions:
        lines.append("The reviewer's verdicts:")
        lines.append("")
        for decision in manifest.decisions:
            marker = " — needs evidence" if decision.needs_evidence else ""
            lines.append(
                f"- `{escape_markdown(decision.feedback_id)}`: "
                f"{escape_markdown(decision.verdict)}{marker}, "
                f"by {escape_markdown(decision.operator)}"
            )
    else:
        lines.append("The reviewer decided nothing in this binding.")
    lines.append("")
    accepted = sum(1 for d in manifest.decisions if d.verdict == "accepted")
    rejected = sum(1 for d in manifest.decisions if d.verdict == "rejected")
    pending = sum(1 for d in manifest.decisions if d.verdict == "pending")
    partly = sum(1 for d in manifest.decisions if d.verdict == "partly_accepted")
    lines.append(
        f"Verdict summary: {accepted} accepted, {partly} partly accepted, "
        f"{rejected} rejected, {pending} pending."
    )
    lines.append("")
    lines.append("Unresolved opinions — the explicit tasks this round leaves open:")
    lines.append("")
    if manifest.unresolved:
        for task in manifest.unresolved:
            lines.append(
                f"- `{escape_markdown(task.feedback_id)}` — "
                f"{escape_markdown(task.reason)}: {escape_markdown(task.detail)}"
            )
    else:
        lines.append(
            "None. Nothing in this round asks for an experiment, a reference or "
            "data the manuscript does not carry."
        )
    lines.append("")
    lines.append(
        "**The two sections above are decided separately.** Drafts published and "
        "receipts recorded do not close the science; an unresolved opinion does "
        "not make the files less delivered."
    )
    lines.append("")
    return "\n".join(lines).encode()
