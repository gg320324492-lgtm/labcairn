# LC-P2-11 — the assessment door resolves the key it is given

**Work order:** the chain's fourth ring, `followup_assessments`, records a
later judgement about an issue. Before the ring could be filled with the
owner's first real judgements, the door had to stop accepting a judgement
about an issue nothing holds. **This record covers that precondition.** The
judgements themselves are not here, and §4 says what is missing before they
can be.

**Measured on the tree this landed in,** `docs/debt-closures`: the door in
`c96928d`, the merged-tree run §3.4, and the record committed after both. The
numbers below belong to that tree.

## 1. The hole, confirmed by execution rather than by reading

`record_assessment` requires that **either** `feedback_id` **or** `issue_key`
be present, and then validates **only** `feedback_id`. `issue_key` is a bare
`String(200)` column on `followup_assessments` — no foreign key — and the door
never asked the chain whether it held that key. The asymmetry is the finding,
and it was run out on a **copy** of the pilot store
(`E:\labcairn-local\tmp\assess-door\pilot-ws-copy\labcairn.db`, made with
sqlite3's `backup()` from a `mode=ro` connection — it measures 48,115,712 bytes
now against the 48,111,616 its author recorded at creation, one page larger,
which is what the rows it then wrote do; the number carried below is the one
that was verified here):

| Given to the unpatched door | What it did |
|---|---|
| `issue_key` naming no case in any table | **ACCEPTED — the row committed** |
| `issue_key` spelled as a revision key, holding no change | **ACCEPTED** |
| a real `issue_key` from a *different* project | **ACCEPTED** |
| `feedback_id` naming no feedback event | REFUSED `chain_feedback_not_found` |

The refusal that existed and the acceptance that did not:

> `chain_feedback_not_found`: the store holds no feedback event with the id
> 'fb-no-such-feedback-in-any-table'. An assessment about a comment nobody
> holds is an assessment about nothing.

> *no refusal at all* — a judgement about nothing entered the table.

**The original store was not touched.** Its SHA-256 was taken before the
demonstration and after: `0db2e3a3e4976aa8c486a20baeaf2a9ef7a6ac2142b5165df4002976cd5be167`,
identical. Every write went to the copy.

## 2. The shape, and why a foreign key cannot hold it

One foreign key cannot cover both kinds of case: **a case is either a comment
or a change, and the two live in different tables** — `feedback_events.issue_key`
and `revision_events.revision_event_id`. So the door resolves the key.

**The route is taken by looking, never by spelling.** A comment's issue key is a
person's judgement and may be spelled any way at all, *including with the prefix
the product's own revision ids carry*. The resolution therefore tries the
comments bound to the key first and the change the key names second, and it is
scoped to the project being assessed — two projects may each hold `"stats"`
without their being one problem. **That is the same order
`labcairn.guidance.retrieval._living_sources` takes**, and it was checked
against the retrieval's own code rather than asserted; if the two ever disagree
about which kind a key is, the same judgement would be reachable by one path and
refused by the other.

A new reason of its own, `ASSESSMENT_ISSUE_NOT_FOUND` →
`chain_assessment_issue_not_found`, registered in `CHAIN_REFUSALS` — the seam
witness that every chain refusal has a layer name is what keeps a surface from
speaking a raw enum name. A key that is present but blank is refused
`arguments_invalid` rather than reaching the chain, because empty and whitespace
would otherwise be *unresolvable* and would answer with the chain's reason for
the wrong question.

## 3. What was measured, and by whom

**This was measured by re-running it, not by reading the window's report.** The
work was done in its own worktree, branched behind the version read; it was
merged at `c96928d`, and the merged tree was then verified here.

### 3.1 The witnesses

**Eight**, all in `tests/test_followup_assessments.py` — the file was extended,
not added to, so no new shard cost had to be bought: an issue the chain does not
hold is refused; a comment key it holds still records; a revision key it holds
records; a revision key it does not hold is refused; a case held only in another
project is refused; the key is routed by lookup and not by its spelling; a blank
key beside a comment is refused; and an assessment naming a comment records
without a key, so the good path is not collateral.

*(One report counted seven. The tree has eight: `git diff` and the witness
ledger agree on 8, and the count in the report was simply wrong. It is the kind
of error the ledger exists to catch — a number carried forward instead of
re-measured.)*

### 3.2 The mutations, re-run here

Baseline green first (15 passed), tree green again after every restore, restored
tree green at the end — **no result was read while the baseline was red.** Each
mutation is an expression swap, never a deleted assertion.

| Mutation | Witnesses that went red |
|---|---|
| M1 a non-empty key is let through (the hole exactly as it stood) | 5 |
| M2 routed by the key's prefix, never looked up | 4 |
| M3 the comment route is checked and the revision route is not | 3 |
| M4 both routes are queried, but the change's project is not asked | 1 |
| M5 the comment route is queried **without its project bound** | 1 |

**M5 is a mutation the author's own battery did not contain**, and it is the
interesting one: it breaks only the comment path, and the cross-project witness
caught it anyway. `test_a_case_held_only_in_another_project_is_refused` does not
depend on which route the key takes, which is what makes it a witness of the
scoping rather than of one branch of it. **The project check is also not
reachable through `_chain_holds_issue_key` alone** — the argument named by a
test cannot be forged, and a caller cannot hand it an `issue_key` while
`feedback_id` stays `None`, so the door's real path is the only one to
measure.

### 3.3 The gates

`ruff check .` clean; `ruff format --check .` clean; `mypy --strict src tests`
clean over 389 source files; the refusal-seam witness green with the new member
in the mapping, so the registration was checked by the witness that reads it,
not asserted by the code that adds it.

### 3.4 On the merged tree, after the merge

`tests/test_followup_assessments.py`, `tests/test_guidance_rules.py`,
`tests/test_application_layer.py`, `tests/test_feedback_events.py` together:
**201 passed** (`c96928d`). The witness ledger over the merge: 3283 functions
before, 3291 after, **LOST — none**, the eight additions named.

## 4. What this piece does not do

**The fourth ring is still empty.** `followup_assessments` holds **zero rows**
in the pilot store — counted directly, read-only, not read out of a report. The
door is now safe to fill; filling it is a separate piece of work.

**What that work needs, in order.** Each rule's standard has to be looked for in
a *later* version of the same manuscript, and the judgement recorded through
this door with `basis="revised_manuscript"`, an `evidence_refs` naming a real
address, and a grade decided case by case — `observed` where the later draft
shows the thing, `inferred` where it shows something close.

**All four projects can carry it, and a belief held going into this record was
wrong about that.** Measured read-only against the store just now:
`version_edges` holds **51** edges, and each project's chain is complete —
`proj-pilot-1` 17 versions / 16 edges, `proj-pilot-2` **3 versions / 2 edges**,
`proj-pilot-3` 23 / 22, `proj-pilot-4` 12 / 11, each with every version
reachable from the first. **`proj-pilot-2` was expected to be unlinked**, and the
plan had set it aside on that ground; it is not, so the fourth ring's first pass
covers four projects, not three. (The fourth pilot's ingest ran idempotently
after a failed first attempt, and the second pilot's edges were added in the same
round; neither is visible from the version counts alone.)

**The rules bound to revision cases — eight of the twenty-four — reach the ring
only through `issue_key`**, which is why the hole had to close first.

**And one thing this correction found elsewhere.** The window's notes named
`web/src/RoundsPanel.test.tsx` as a witness of the workbench's closed limits.
**No such file exists.** The real ones are `web/src/views/EventsView.test.tsx`
and `web/src/app/workbench.test.tsx`, and the search that replaced the name is
the same search that found three documents still asserting a limit `37591c7`
had closed the day before — including this handoff's own `CURRENT.md`, dated
2026-11-03. That correction landed separately; see [the release
notes](../RELEASE-NOTES.md) §2.5 and §2.6 and [QUICKSTART
§6](../QUICKSTART.md).
