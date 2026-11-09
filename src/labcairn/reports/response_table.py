"""The point-by-point response table: the deliverable that shows the loop.

**What this module is.** One of LC-P3-04's four deliverables: the table that
lays out, for every supported input opinion, where the opinion sits — its
location, the suggestion the model put forward, the verdict the reviewer
gave, the change that landed, and the state the chain holds. It is the
offline counterpart of execution plan §4's *point-by-point response* row,
and its whole claim is **completeness**: an opinion absent from the table is
an opinion silently dropped, which is the one outcome this ticket exists to
make impossible.

**The table is built from the dossier manifest, not from a caller's
summary.** The manifest is the binding's own record of what happened; a
caller-passed summary would be a second spelling of the same facts, and the
two would drift.

**Every text value is escaped, and the writer is LabCairn's own.** ADR-0013
decided the report library boundary, and this module stays inside it: the
Markdown is written here with :func:`escape_markdown` on every retrieved
string, because a comment's text is data and never instructions — a comment
that says ``# Not a heading`` must not become one in the file.
"""

from __future__ import annotations

from typing import Final

from labcairn.reports.render.markdown import escape_markdown

__all__ = [
    "RESPONSE_TABLE_COLUMNS",
    "render_response_table_markdown",
]


#: The table's columns, in the order a reader meets them. The order is part
#: of the deliverable: the same opinion reads the same way in every table
#: this build produces.
RESPONSE_TABLE_COLUMNS: Final[tuple[str, ...]] = (
    "Opinion",
    "Location",
    "Suggestion",
    "Verdict",
    "Change",
    "Chain state",
)

#: The words an empty cell carries. An empty cell is not silence — the cell
#: says why it is empty, so a blank never has to be interpreted.
NOTHING_SUGGESTED: Final[str] = "none proposed"
NO_CHANGE: Final[str] = "no change applied"


def render_response_table_markdown(manifest_json: str) -> bytes:
    """The response table, as Markdown bytes, from one dossier manifest.

    :param manifest_json: the dossier manifest's own JSON — the bytes the
        binding wrote, parsed here rather than re-derived.
    :returns: the table, UTF-8. The same manifest gives the same bytes,
        every time: the table is a pure function of the manifest.
    """
    from labcairn.papers.binding import (
        DecisionEntry,
        OpinionEntry,
        ResponseEntry,
        SuggestionEntry,
    )

    manifest = DossierManifest.model_validate_json(manifest_json)

    suggestions = {entry.feedback_id: entry for entry in manifest.suggestions}
    decisions = {entry.feedback_id: entry for entry in manifest.decisions}
    responses = {entry.feedback_id: entry for entry in manifest.responses}

    lines: list[str] = []
    lines.append("# Point-by-point response table")
    lines.append("")
    lines.append(f"Input version: `{escape_markdown(manifest.input_version_id)}`")
    lines.append(f"Output version: `{escape_markdown(manifest.output_version_id)}`")
    lines.append(f"Marked draft receipt: `{escape_markdown(manifest.marked_receipt_id)}`")
    lines.append(f"Clean draft receipt: `{escape_markdown(manifest.clean_receipt_id)}`")
    lines.append("")
    lines.append("| " + " | ".join(RESPONSE_TABLE_COLUMNS) + " |")
    lines.append("|" + "|".join("---" for _ in RESPONSE_TABLE_COLUMNS) + "|")

    for opinion in manifest.opinions:
        suggestion = suggestions.get(opinion.feedback_id)
        decision = decisions.get(opinion.feedback_id)
        response = responses.get(opinion.feedback_id)
        lines.append(
            "| "
            + " | ".join(
                (
                    escape_markdown(opinion.feedback_id),
                    escape_markdown(_location_cell(opinion)),
                    escape_markdown(_suggestion_cell(suggestion)),
                    escape_markdown(_verdict_cell(decision)),
                    escape_markdown(_change_cell(response)),
                    escape_markdown(_state_cell(response)),
                )
            )
            + " |"
        )

    lines.append("")
    lines.append("## Unresolved opinions")
    lines.append("")
    if manifest.unresolved:
        for task in manifest.unresolved:
            lines.append(
                f"- `{escape_markdown(task.feedback_id)}` — "
                f"{escape_markdown(task.reason)}: {escape_markdown(task.detail)}"
            )
    else:
        lines.append("None. Every supported opinion is resolved in this table.")
    lines.append("")
    lines.append("## Handovers")
    lines.append("")
    if manifest.handovers:
        for handover in manifest.handovers:
            lines.append(
                f"- `{escape_markdown(handover.feedback_id)}` — "
                f"{escape_markdown(handover.reason)}: {escape_markdown(handover.handover)}"
            )
    else:
        lines.append("None. The seam applied every approved edit.")
    lines.append("")
    return "\n".join(lines).encode()


def _location_cell(opinion: OpinionEntry) -> str:
    """What the Location column says about one opinion."""
    paragraph = (
        f", paragraph {opinion.anchor_paragraph}" if opinion.anchor_paragraph is not None else ""
    )
    return f"{opinion.location_state} (anchor {opinion.anchor_status}{paragraph})"


def _suggestion_cell(suggestion: SuggestionEntry | None) -> str:
    """What the Suggestion column says, when the source proposed one."""
    if suggestion is None:
        return NOTHING_SUGGESTED
    return f"paragraph {suggestion.paragraph}, by {suggestion.author}"


def _verdict_cell(decision: DecisionEntry | None) -> str:
    """What the Verdict column says, when the reviewer decided."""
    if decision is None:
        return "not reviewed"
    verdict = decision.verdict + (" — needs evidence" if decision.needs_evidence else "")
    return f"{verdict}, by {decision.operator}"


def _change_cell(response: ResponseEntry | None) -> str:
    """What the Change column says, when the chain holds the change."""
    if response is None:
        return NO_CHANGE
    return response.edit_action_id


def _state_cell(response: ResponseEntry | None) -> str:
    """What the Chain state column says, when the chain holds a judgement."""
    if response is None:
        return NO_CHANGE
    return response.state
