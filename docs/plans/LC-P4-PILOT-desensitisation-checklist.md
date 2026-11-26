# LC-P4-PILOT — desensitisation checklist for the pilot paper

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Status:** `CONFIRMED — the owner signed item D-6 on 2026-11-25`

**How to confirm.** The advisor (as data owner) works the checklist
top to bottom on the desensitised copy and ticks every item A-1…A-7,
B-1…B-4, C-1…C-4, D-1…D-6 and the part-E acceptance checks. Items D-1…D-5
are **registered**, not ticked: they are fields of the registration record
described in part D, written and measured by
[`scripts/pilot_material_registration.py`](../../scripts/pilot_material_registration.py).
The ticks are recorded in item D-6's checklist result — the date, the
operator, the per-item pass/fail and the digest the result applies to —
which is the same record's `checklist.result`, and the part-E result is
attached to the pilot ticket's material pointer record. **Until the owner
has signed that result, the import step (plan §9.2 step 2) must not run
and no copy enters the pilot.** The signature goes on the D-6 result; this
document stays `DRAFT` until then.

**The owner signed it on 2026-11-25**, on the copy registered as
`pilot-paper-002` (sha256
`04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`):
every item A-1…A-7, B-1…B-4, C-1…C-4 and D-1…D-5 is recorded as `pass`,
and the result is bound to that digest — so it applies to that copy and to
no other. The readings the signature rests on are in
[`docs/acceptance/LC-P4-PILOT-desensitisation-measurement-2026-11-25.md`](../acceptance/LC-P4-PILOT-desensitisation-measurement-2026-11-25.md),
and the copy that was signed is the one that keeps the advisor's revision
trail. **The part-E acceptance checks are still the pilot ticket's own**,
and the import step (plan §9.2 step 2) may now run against the signed
copy.
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

**Half of this checklist is measurable, and the measurement is a tool.**
[`scripts/pilot_desensitisation_check.py`](../../scripts/pilot_desensitisation_check.py)
reads the copy and the original it was derived from, computes the readings
this checklist asks for — the property states, the revision counts, the
comment counts, the digests — and reports every item with a verdict. The
items whose evidence a machine cannot read (a byline, an affiliation
sentence, a numbering's continuity) stay `undecided` and are marked as
needing a person, so a reading is never mistaken for a pass. The tool's
`--require-signed` mode fails while item D-6 carries no signature. The
readings it took on the registered copy are in
[`docs/acceptance/LC-P4-PILOT-desensitisation-measurement-2026-11-25.md`](../acceptance/LC-P4-PILOT-desensitisation-measurement-2026-11-25.md).

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
| C-4 | One desensitisation pass, one copy | The pilot uses a single named copy; re-desensitising mid-pilot invalidates digests and version anchors | The copy's material id and digest are registered once (item D); any later change to the copy restarts this checklist and re-registers the digest |

## D. Registration — what the repository keeps

**Where the registration lives.** One JSON record per copy, under
`docs/pilot/registrations/`, named for the material id
(`docs/pilot/registrations/pilot-paper-001.json`). The format is stated in
[`../pilot/README.md`](../pilot/README.md), and the record is written and
checked by
[`scripts/pilot_material_registration.py`](../../scripts/pilot_material_registration.py)
— the same shape as the release records: a structured file under a known
name, a tool that fills it by measuring, and a checker that refuses an
incomplete one. **The repository holds no material.** The record carries
ids, digests, counts, paths and a name; it has no free-text field at all,
so there is nowhere for a sentence of the manuscript to go.

| # | Item | Registered value | Field in the registration record |
|---|---|---|---|
| D-1 | Material id | The pilot's stable id for the copy (e.g. `pilot-paper-001`), used by every later record that points at the material | `material_id` |
| D-2 | Source authorisation | A pointer to the owner's authorisation for using this paper (who authorised, what scope) — a path/record id, not a copy of the paper | `authorisation` (`grant_id`, `record`, `subject_ref`, `scope`, `granted_by`, `granted_at`, `expires_at`) — read out of the authorisation record the citation names, never typed |
| D-3 | Metadata set | File format, page/word/figure/table counts, comment count, revision-mark count, heading outline digest — counts and digests only, no content | `copy.format` and `metadata` (the seven counts and the outline's digest) |
| D-4 | Material fingerprint | sha256 of the desensitised copy, plus the digest of the original it was derived from (G0 §4 records the standing candidate's digest the same way) | `copy.sha256` and `copy.origin_sha256`, with each file's byte size |
| D-5 | Storage path | The authorised-environment path (`E:/trial-material/…`) where the copy lives — a path only; the repository stores no bytes of the material | `storage.root` and `storage.relative_path` |
| D-6 | Checklist result | Date, operator, per-item pass/fail, and the digest this result applies to (C-4's single-pass rule) | `checklist.result` — **the owner's, and empty until the owner writes it** |

**Who writes what.** The tool measures what can be measured — the copy's
and the original's sha256, the heading outline's digest and its heading
count — and writes down the counts the operator supplies. **The grant is
read out of the authorisation record the record cites**, not typed: the
tool finds the grant in that file whose scope covers the copy and copies
its fields, so the check cannot be satisfied by a claim. The tool leaves
the checklist result **empty**: D-6 is the owner's to write, and the
owner's signature is one act (`sign`, which measures the copy, reads the
item ids out of this checklist, refuses a set that misses one or carries
one this checklist does not have, and stamps the result with the digest of
the copy that is registered — so a signature cannot drift onto another
copy). Until that result is there, `check --require-signed` fails, and the
import step (plan §9.2 step 2) must not run.

**Which copy.** The record registers whichever copy the owner picks; the
format decides nothing. G0 §4 names the standing candidate — the Phase 3
trial's advisor-annotated working sample, sha256 `a7a38132…`, 8,871,367 B,
measured 2026-11-21/22 against the T1 supply receipt — and calls it the
standing candidate. **The pilot's final material choice is the owner's**
(G0 §4; recorded in the pilot ticket when P4-PILOT opens). The standing
candidate is the natural default and nothing more: the record is written
when the owner says which copy it is, and the copy has to live where the
signed grant's scope reaches.

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
