# LC-P4-PILOT — desensitisation checklist for the pilot paper

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Status:** `DRAFT — for owner confirmation before P4-PILOT opens`

**How to confirm.** The advisor (as data owner) works the checklist
top to bottom on the desensitised copy and ticks every item A-1…A-7,
B-1…B-4, C-1…C-4, D-1…D-6 and the part-E acceptance checks; ticks are
recorded in item D-6's checklist result (date, operator, per-item
pass/fail, digest) and the part-E result is attached to the pilot
ticket's material pointer record. **Until the owner has signed that
result, the import step (plan §9.2 step 2) must not run and no copy
enters the pilot.** The signature goes on the D-6 result; this document
stays `DRAFT` until then.
**Source plan:** [`PHASE_4-execution-plan.md`](PHASE_4-execution-plan.md) §9.1
(pilot material) and §9.2 step 1–2 (import, digest check).
**Boundary source:** [`LC-P4-G0-baseline-freeze.md`](LC-P4-G0-baseline-freeze.md)
§4 (material pointer, no-material boundary).

This checklist turns plan §9.1's desensitisation requirement — *retain
annotations, revision marks and structure; remove names, affiliations,
project numbers and other unnecessary sensitive information* — into
checkable items. **Read 2026-11-25** from
`docs/plans/PHASE_4-execution-plan.md` §9.1; the paraphrase is the
plan's own requirement carried into English, and the section number says
where the wording lives. It covers the path from an authorised paper to
the desensitised working copy the pilot imports, and the registration of
the copy's digest and metadata. **The repository never receives the
material itself** — raw files stay in the authorised environment
(`E:/trial-material/`), and this checklist's records carry digests, counts,
ids and paths only, per G0 §4.

**How to use:** work top to bottom. Every item has a pass/fail check that
one person can execute before the copy enters the pilot. Item D-3
(metadata fields) and item E (digest registration) are the two items the
import step (plan §9.2 step 2) verifies again on its side; the pilot does
not re-desensitise, it refuses a copy that fails either check.

## A. Removal items — nothing on this list may survive into the copy

| # | Item | Where it hides | Check (executable) |
|---|---|---|---|
| A-1 | Author names | Title block, byline, footnotes, headers/footers, document properties (`Author`, `Last Modified By`) | Search the visible text for every author name on the original's byline; open File ▸ Info and read the `Author` and `Last Modified By` properties; all must be blank or replaced by a fixed pseudonym before import |
| A-2 | Affiliations and addresses | Title block, author notes, first-page footnote, email lines | Search for the affiliation string, department, street address, and every `@`-address in the body and footnotes; each hit must be removed or replaced |
| A-3 | Project/grant numbers | Funding footnote, acknowledgements, cover page | Search for the grant/project number patterns recorded on the original's funding statement (and the funding agency's name); no hit may remain in text, footnotes, or headers |
| A-4 | Acknowledgements section | Back matter | The acknowledgements section is deleted in full — a partial edit leaves collaborator names; the section's absence is the pass condition |
| A-5 | Collaborator identities inside text | References to "the first author", named colleagues, lab names, instrument site names | Read the body for self-references that identify people or the group; rewrite to neutral phrasing |
| A-6 | Contact and identity metadata | Document properties, custom properties, comments' author fields, revision-history author fields | List every document property (built-in and custom); every person- or project-bearing value is blanked. Comment and tracked-change author names are replaced by role labels (e.g. `advisor`, `student-1`) — see C-2 |
| A-7 | Embedded identifiers | Figure/image metadata, embedded-object properties, filename itself | Strip EXIF/author metadata from embedded images where the tooling allows; the copy's filename carries no author, project, or title-of-record — it uses the pilot's material id |

A hit found during the check is fixed in the working copy and re-checked;
the check is repeated until A-1…A-7 all pass on the same copy.

## B. Retention items — these must survive desensitisation intact

| # | Item | Why the pilot needs it | Check (executable) |
|---|---|---|---|
| B-1 | Advisor annotations (comments) | The opinions the pilot parses and traces (plan §9.2 step 1–2; G0 §6 `Opinion.source_locator`) | Count comments in the original and in the copy — the counts match; spot-check three comments' anchor text and location |
| B-2 | Revision marks (tracked changes) | The revision trail the pilot's trajectory view and the multi-source line depend on | Turn on "show all markup": insertions, deletions and format changes are present, and their count matches the original's recorded count |
| B-3 | Paper structure | Section numbering, headings, figure/table numbering, references — the deliverables must map onto the real paper's shape | Compare the heading outline of original and copy (same headings, same order, same levels); the outline match is the pass condition |
| B-4 | Content needed by the loop | Abstract, body, figures/tables with captions, reference list | The copy's page/word counts are within a small delta of the original's (the delta equals only the removed A-items); no section body is blanked |

## C. Format and trace handling

| # | Item | Rule | Check (executable) |
|---|---|---|---|
| C-1 | Comment text stays in the copy | The annotations are pilot input, not leakage — only *authorship* of comments is desensitised (A-6) | Open the copy's comment pane: comment bodies are readable and anchored; author labels are role labels |
| C-2 | Revision authorship relabelled | Tracked-change and comment authors become role labels; dates may stay (they carry no identity) | The revision list shows only the role-label author set; no original person name appears in any markup author field |
| C-3 | No new content invented | Desensitisation removes or neutralises; it does not rewrite science | Diff the copy against the original: every difference is attributable to an A-item removal or a C-2 relabel; anything else is a defect in the copy |
| C-4 | One desensitisation pass, one copy | The pilot uses a single named copy; re-desensitising mid-pilot invalidates digests and version anchors | The copy's material id and digest are registered once (item E); any later change to the copy restarts this checklist and re-registers the digest |

## D. Registration — what the repository keeps

| # | Item | Registered value |
|---|---|---|
| D-1 | Material id | The pilot's stable id for the copy (e.g. `pilot-paper-001`), used by every later record that points at the material |
| D-2 | Source authorisation | A pointer to the owner's authorisation for using this paper (who authorised, what scope) — a path/record id, not a copy of the paper |
| D-3 | Metadata set | File format, page/word/figure/table counts, comment count, revision-mark count, heading outline digest — counts and digests only, no content |
| D-4 | Material fingerprint | sha256 of the desensitised copy, plus the digest of the original it was derived from (G0 §4 records the standing candidate's digest the same way) |
| D-5 | Storage path | The authorised-environment path (`E:/trial-material/…`) where the copy lives — a path only; the repository stores no bytes of the material |
| D-6 | Checklist result | Date, operator, per-item pass/fail, and the digest this result applies to (C-4's single-pass rule) |

Registration happens in the pilot ticket's material pointer record when
P4-PILOT opens (G0 §4: *the pilot's final material choice is the owner's,
recorded in the pilot ticket*). This checklist's filled result is the
evidence attached to that record.

## E. Acceptance of the copy at import

The import step (plan §9.2 step 2 — *check the original file's digest and
version information*) re-verifies, on the pilot's side:

1. The copy's sha256 equals D-4's registered digest (a mismatch means the
   copy changed after desensitisation — C-4 applies).
2. The metadata counts of D-3 match what the import observes (comment
   count, revision-mark count, structure outline).
3. No A-item pattern resurfaces: the import runs the A-1/A-2/A-3 searches
   once more on the incoming file and refuses the copy on any hit.

A copy that passes E is the pilot's working material. A copy that fails any
E check is returned to the desensitisation step with the failing item named.
