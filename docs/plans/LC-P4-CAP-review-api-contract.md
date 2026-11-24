# LC-P4-CAP review-API contract — the workbench↔service interface, v1

**Status:** agreed by both windows, 2026-11-23. Window A (backend) implements
it; Window B (web) builds the three-column workbench against these shapes
with fixture data until the service is up.

**Principle kept from the existing layer:** the API never touches the store
directly — every route calls an application-layer operation, and the
permission ask lives where the material is named. The chain's own facts
(`read_comments` / `read_edits` / `read_response_states`) and the paper
reads (`list_versions` / `list_edges`) already exist and are reused, not
re-spelled.

## Endpoints (all under the existing session-token guard; paths follow the
service's existing spelling style — singular nouns, verb tails)

### 1. `GET /review/opinions?project_id=…&version_id=…`

The opinion list the left column renders, with everything the middle and
right columns need per opinion.

Response `ReviewOpinions`:

```jsonc
{
  "project_id": "…",
  "version_id": "…",
  "opinions": [
    {
      "feedback_id": "fb-…",
      "issue_key": "…",            // may be "" until a person names one
      "version_id": "…",           // the version the comment was written against
      "comment_text": "…",         // the advisor's words
      "author": "…",               // may be null
      "anchor_status": "resolved | unknown | position",
      "anchor_reason": null,       // why unknown, when unknown
      "anchor_paragraph": 12,      // 1-based; null when unplaced
      "anchor_start": 0,           // half-open span into the anchored text
      "anchor_end": 45,
      "anchor_text": "…",          // the baseline text the span is into; null when none
      "comment_locator": { … },    // the DocxLocator JSON, or null on an unread row
      "location_state": "located | needs_evidence | uncertain_location",
      "suggestion": {              // null when no suggestion exists yet
        "part": "word/document.xml",
        "paragraph": 12,
        "old_text": "…",           // the whole run's text the seam would rewrite
        "new_text": "…",
        "author": "model:…",
        "proposed_at": "2026-11-23T…"
      },
      "decision": {                // null when not yet reviewed
        "verdict": "accepted | partly_accepted | rejected | pending",
        "operator": "…",
        "decided_at": "…",
        "needs_evidence": false
      },
      "response_states": ["addressed | partially_addressed | not_addressed | pending"]
    }
  ]
}
```

Sources: `application.chain.read_comments` + `papers.feedback.list_feedback_events`
(joined by `feedback_id`), `binding.open_binding`'s classification for
`location_state`, the store's suggestion rows for `suggestion`,
`binding`'s decision records for `decision`, `read_response_states` for the
chain's states. **A suggestion and its decision are never merged into one
record** — they are separate fields, ADR-0016's rule at the API's surface.

### 2. `GET /review/manuscript?project_id=…&version_id=…`

The middle column's text, in paragraphs, with the anchors resolvable.

Response `ReviewManuscript`:

```jsonc
{
  "project_id": "…",
  "version_id": "…",
  "sha256": "…",                 // the version's content hash
  "paragraphs": [
    { "index": 1, "text": "…" }  // 1-based, document order, accepted view
  ]
}
```

Read through the existing DOCX reader (`material.ooxml.read_document`) under
`CapabilityId.SOURCE_READ` with the same `max_bytes` bound the feedback path
uses. **No prose leaves the manuscript path**: this returns the version's own
paragraph text and nothing else.

### 3. `POST /review/decision`

One person's verdict on one opinion's suggestion. Body:

```jsonc
{
  "project_id": "…",
  "feedback_id": "fb-…",
  "verdict": "accepted | partly_accepted | rejected | pending",
  "needs_evidence": false,
  "operator": "…"               // the human's handle; decided_by stays "user"
}
```

Writes a `binding.ReviewDecision` row (`decided_by="user"`, `decided_at`
from the service clock). **Refuses** an unknown `feedback_id`, and refuses
a `partly_accepted`/`accepted` verdict whose suggestion does not exist (a
verdict on nothing would be approval theatre). Returns the decision record.

### 4. `POST /review/apply`

Run the approved set through the seam and close the binding — the existing
`apply_approved_edits`, called with the decisions the store holds. Body:

```jsonc
{
  "project_id": "…",
  "input_version_id": "…",
  "source_root_id": "…",
  "source_key": "…",
  "output_label": "…",
  "window_end": "…"             // the approvals' expiry, ISO-8601
}
```

Response: the `BindingClosed` shape flattened — publications' receipts,
output version id, edge id, per-opinion edit/refusal lists, the four
deliverables' artifact ids (`marked`, `clean`, `response_table`,
`quality_report`), and the dossier's artifact id.

**Idempotence:** a second call with the same input version and the same
decision set must not produce duplicate publications — the loop's existing
duplicate/staleness guards are the mechanism, and the route adds none.

## What window B may assume

- Every list is ordered: opinions in document/anchor order, paragraphs in
  document order.
- `anchor_paragraph` is 1-based and matches the manuscript endpoint's
  `index`, so scroll-sync is a equality test, not a lookup.
- Errors come back as the service's existing refusal vocabulary
  (`reason` + `message`), never as bare 500s.
- Until the service route exists, B builds against `fixtures/review-sample.json`
  carrying these exact shapes (committed with B's work, deleted when the
  service answers).

## What this contract deliberately does not cover (next batches)

- Real-model suggestion generation (P4-CAP §7.2) — the suggestion source
  stays injectable; this batch's API reads what the store holds.
- Apply/publish previews (the plan's pre-apply preview) — batch 2.
- Multi-source learning endpoints (P4-MS) — after the delivery loop.
