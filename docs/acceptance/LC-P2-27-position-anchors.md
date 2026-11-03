# LC-P2-27 — The anchor that covers no text is stored as covering no text

**Work order:** SOW (1) plan b, decided by the owner · **Status:** LANDED
on `claude/anchor-position-06df0`, every claim mutation-checked locally.
The real pilot store was **never written**: it is read-only for this piece,
and its data correction is a separate work order awaiting the owner's
approval.

## 1. The defect this closes

`FeedbackEventRow.anchor_status` had two words: `resolved` and `unknown`.
Two checks then forced a lie onto every row whose anchor covered no text:

- `feedback_events_anchor_is_resolved_or_named` demanded that an
  `unknown` row drop `anchor_start`/`anchor_end` — so a comment the
  reader *did* place on a position lost the place it was placed at;
- `feedback_events_ids_present` demanded
  `length(anchor_text_sha256) > 0` — so every row without anchored text
  stored the digest of the empty string as the integrity value of a text
  that is not there.

The reader reported a zero-width range (a comment whose range closes
where it opens — a comment on *the place*, not on words) as `unknown`
with `POSITION_ANCHOR_REASON`. That kept the two shapes apart at the
reader, but the store could not hold the fact: thirteen rows of the pilot
store carry `unknown` + that reason, and every one of them stores
`e3b0c442…b855` in a column that reads as an integrity value.

**Why plan b (a third status) and not a nullable digest on `unknown`.**
A position is *placed, not unknown*: the reader found where the comment
sits, and the file records no words there. Widening `unknown`'s shape to
let it keep an offset would make "unknown" mean both *could not place*
and *placed on nothing* — the exact conflation the scope lead
(`_POSITION_ANCHOR_LEAD`) exists to refuse. The third word keeps the
three facts three: resolved (text, at a place), unknown (a reason, no
place), position (a place, no text).

## 2. What landed

**The schema** ([`models.py`](../../src/labcairn/db/models.py),
[`0023_position_anchors.py`](../../migrations/versions/0023_position_anchors.py)):

- `anchor_status` vocabulary: `resolved`, `unknown`, `position`.
- `anchor_text` and `anchor_text_sha256` are nullable, and the new shape
  check `feedback_events_anchor_shape_matches_status` pins them per
  status:
  - `resolved`: paragraph, start and end present, reason `NULL`,
    **`anchor_text` non-empty and digest present** — the claim the
    sixteen pilot rows made (resolved over no text) is now refused by the
    schema, not only by the door;
  - `unknown`: reason present, start/end `NULL`, **text and digest
    `NULL`**;
  - `position`: paragraph, start and end present, **`start = end`** (a
    position is a range that closes where it opens — the equality is the
    definition, written into the check), reason `NULL`, text and digest
    `NULL`.
- `anchor_reason` on a `position` row is `NULL`, by design: the reason
  column's meaning is *why the anchor is unknown*, and a position is not
  unknown — there is no failure to explain. The fact "this is a place,
  not a passage" is carried by the status itself; saying it twice in two
  columns would give the second copy nothing to do. `POSITION_ANCHOR_REASON`
  stays exported: the thirteen legacy rows carry it, and the distil
  compatibility path reads it (§3).
- `feedback_events_ids_present` drops the digest clause — the digest is
  pinned by status in the shape check, where it belongs.
- `reply_settlements.anchor_status` is untouched: its two words mean
  *the judgement points at a manuscript address or does not*, which is a
  different axis from the feedback row's anchor, and nothing in this piece
  concerns it.

**The migration.** SQLite cannot alter a check, so the table is rebuilt
in batch mode, and the rebuild happens in three steps because the new
check cannot install over data that denies it:

1. widen the two columns, drop the three old checks;
2. **clean the placeholder**: `UPDATE … SET anchor_text = NULL,
   anchor_text_sha256 = NULL WHERE anchor_status = 'unknown'` — the two
   columns the old shape invented values for, and nothing else;
3. create the three new checks.

Each cleaning runs in the window between the checks it must satisfy, and
the downgrade runs the same way — the shape checks drop first, the rows
re-spell, the old checks restore: a row's end state, not its intermediate
one, is what each check meets.

This is the shape of revision 0012's backfill: a data move that makes the
new constraint installable, scoped to exactly the columns it exists for.
**The downgrade is faithful to the shape it returns to, and that shape
loses the place**: a `position` row downgrades to `unknown` with
`POSITION_ANCHOR_REASON` (what it was called before the third word), and
the old shape has nowhere to keep a placed position's offset, so the
offset goes with the status; the placeholder is written back, because the
shape it returns to refuses a row without one. Upgrading again cleans the
placeholder and does not re-derive the offset — re-casting the row as a
`position` again is the data correction's work, and the downgrade test
asserts the loss rather than pretending the round trip kept it.

**What the migration deliberately does not touch** — and the record this
makes for the data-correction work order:

- **Resolved rows whose anchored text is the empty string** (the pilot's
  sixteen) are *refused by the new check*. A store that carries them
  cannot be upgraded until they are re-cast — which is the point: the
  schema refuses the claim the sixteen rows make, and the re-casting
  (three reader-drop rows to resolved-with-text, thirteen to `position`)
  needs the file evidence the data correction holds.
- **`unknown` rows whose reason names a position** keep their status and
  reason. The upgrade cleans their placeholder; re-casting them as
  `position` rows is the data correction's decision, not a schema
  revision's.

**The reader** ([`ooxml.py`](../../src/labcairn/material/ooxml.py)): the
zero-width branch now reports `status="position"`, `reason=None`, the
paragraph **and the offset kept** (`start == end == the offset the range
closes at`), and `text=None`. Every no-text branch reports `text=None`
(not `""`): there is no text, and `None` is what that is.
`CommentAnchor.text` is `str | None`; `POSITION_ANCHOR_REASON` is no
longer minted by the reader, and stays exported for the legacy rows.

**The layer** ([`feedback.py`](../../src/labcairn/papers/feedback.py),
[`chain.py`](../../src/labcairn/application/chain.py),
[`trajectory.py`](../../src/labcairn/roles/trajectory.py)):
`FeedbackEvent.anchor_text`/`anchor_text_sha256` and
`ChainComment.anchor_text`/`TrajectoryComment.anchor_text` are
`str | None`, carried through from the row without re-spelling — a
position row reads back as `None`, and a legacy row (cleaned by the
migration) reads back as `None` too. `record_feedback` writes `NULL` for
any anchor that covers no text, and the re-recording comparison
normalises both spellings of "no text" (`_text_of`): `NULL` and the
legacy empty-string digest read as the same fact, so re-recording a
position that has not moved finds the row it recorded, legacy spelling or
new.

**`anchor_state`'s verdict for a position is `unanchored`.** The three
verdicts answer one question — *does this row's anchored text still sit
where the row says it does* — and a position row has no anchored text to
ask about. It is therefore `unanchored`, the verdict a row the reader
could not place also carries, and never `fresh`; a verdict that would
claim a text had been confirmed where no text exists is exactly the false
`fresh` this function exists to refuse. Confirming that the *place* still
sits where it did is a re-reading of the file, which this function does
not do for a row with no text to compare. **The door**
(`ANCHOR_RESOLVED_WITHOUT_TEXT`) is untouched in mechanism and now guards
a narrower gap: the reader reports positions as `position`, so a
resolved-with-no-text anchor reaching the door means a reader regression
or a hand-built claim, and the schema refuses it too — the door is no
longer the only thing standing between the empty digest and the store.

**The distillation** ([`distil.py`](../../src/labcairn/guidance/distil.py)):
the position bucket dispatches on **two spellings of one fact** — the
status (`anchor_status == "position"`) is the reader's current word, the
reason (`anchor_status == "unknown"` with `POSITION_ANCHOR_REASON`) is
the word the legacy rows carry — and both land in the same bucket, under
the same lead. `unplaced` narrows to `unknown` rows whose reason is not
the position reason, so no case changes buckets when the spelling
changes.

## 3. The compatibility requirement, met twice

Every reader of these rows must accept both the new `position` rows and
the legacy `unknown`+reason rows. The two spellings meet in three places,
and each has its own witness:

| Where | Legacy shape | Witness |
|---|---|---|
| the distillation's scope bucket | `unknown` + `POSITION_ANCHOR_REASON`, text and digest `NULL` after the cleaning | `test_a_position_spelled_the_legacy_way_lands_in_the_same_bucket` — the row is re-cast to the legacy spelling in place, and the scope still says *a position, not a passage*, never *could not place* |
| re-recording the same version | a legacy row found by id must not read as stale | `test_a_legacy_row_is_read_and_re_recorded_without_a_false_stale` — the cleaned legacy row is found and returned, not refused |
| `anchor_state` over rows the schema no longer mints | a store still at 0022 under today's code (opening a workspace does not migrate it) holds `resolved` rows over no text | `test_a_row_claiming_an_empty_text_is_never_fresh` — staged on a real 0022 database, the row is `stale`, never the false `fresh` |

## 4. The witnesses, and what each mutation caught

Every witness below was **mutation-checked**: the assertion's mechanism
was broken in source, the witness was re-run, and the red was recorded.
Twelve mutations ran, one per mechanism, and all twelve were caught; the
mutations that were first tried and **not** caught are recorded too,
because a mutation that survives says the witness was watching something
else:

- the first attempt at the re-read guard's mutation targeted
  `test_a_row_claiming_an_empty_text_is_never_fresh`, whose row-side
  guard fires before the re-read is ever reached — the mutation survived,
  and the re-read guard got its own witness
  (`test_a_row_whose_text_the_file_no_longer_holds_is_never_fresh`, a row
  with real text whose re-read names no words) and its own mutation;
- the `_text_of` mutation first ran against a head-schema test, which
  cannot hold the placeholder digest at all — the placeholder re-recording
  is now staged on a real 0022 database
  (`test_a_legacy_row_with_a_forced_placeholder_digest_is_re_recorded`),
  the only shape that can hold it.

All runs used `--basetemp` outside the repository, with `TEMP`, `TMP` and
`TMPDIR` pointed at the same outside directory, one directory per run.

| # | Claim | Witness | Mutation | Red |
|---|---|---|---|---|
| 1 | the reader reports a position with the place kept | `test_a_range_that_closes_where_it_opens_is_a_position_not_a_passage` | status reverted to `"unknown"` | `AssertionError` on the status |
| 2 | the reader reports the over-insertion shape as a position | `test_a_comment_over_inserted_text_is_a_position_in_the_baseline` | offset dropped (`start=None`) | `AssertionError: assert anchor.start is not None` |
| 3 | the store refuses a position row that carries a digest | `test_the_schema_refuses_an_anchor_row_that_does_not_hold_what_its_status_claims` | the check's position branch loses its digest pin | the refused insert was accepted (`DID NOT RAISE`) |
| 4 | a resolved row must carry real text | same witness, `fb-resolved-empty` case | the check's `length(anchor_text) > 0` removed | the empty-text insert was accepted |
| 5 | a position row is recorded with the place and no digest | `test_a_position_anchor_is_recorded_and_never_fresh` | `anchor_hash` computed unconditionally over `anchor.text or ""` | `IntegrityError` — the schema refuses the row the door then wrote |
| 6 | re-recording reads a placeholder digest as "no text" | `test_a_legacy_row_with_a_forced_placeholder_digest_is_re_recorded` | `_text_of` reduced to identity | `ApplicationRefusedError: ANCHOR_STALE` |
| 7 | a resolved row with no text is stale before any read | `test_a_row_claiming_an_empty_text_is_never_fresh` | the row-side guard returns `fresh` | `AssertionError: "stale" != "fresh"` |
| 8 | a re-read that names no words confirms nothing | `test_a_row_whose_text_the_file_no_longer_holds_is_never_fresh` | the re-read guard returns `fresh` | `AssertionError: "stale" != "fresh"` |
| 9 | the legacy spelling of a position lands in the position bucket | `test_a_position_spelled_the_legacy_way_lands_in_the_same_bucket` | the reason branch removed from the dispatch | the scope the cases do not support is refused |
| 10 | the status spelling lands in the same bucket | `test_a_case_that_resolved_to_an_empty_text_is_not_a_case_that_was_never_placed` | the status branch misspelled | the scope the cases do not support is refused |
| 11 | the upgrade cleans the placeholder and moves nothing else | `test_a_store_with_legacy_unknown_rows_upgrades_and_loses_nothing` | the cleaning `UPDATE` deleted from the migration | `IntegrityError` — the new check fails to install over the placeholder |
| 12 | a position downgrades to what it was called | `test_a_position_row_downgrades_to_what_it_was_called_before` | the downgrade's re-spelling `UPDATE` deleted | `IntegrityError` — the restored two-word vocabulary refuses the row |

The mutations ran from a script outside the repository that writes its
one replacement with `read_bytes`/`write_bytes` (never `read_text`, which
rewrites CRLF), re-runs the named witness, and restores the file with
`git checkout --` — the work was committed first, so nothing uncommitted
was ever on the table, and the script asserts the tree is clean
afterwards.

## 5. What is deliberately not here

- **The pilot store's rows are not re-cast.** Thirteen `unknown`+reason
  rows and sixteen resolved-over-no-text rows wait for the data
  correction work order; until it runs, a pilot store cannot be upgraded
  past 0022, and this record is the notice of that.
- **A position's place is not confirmed by `anchor_state`.** Keeping the
  offset is storage; confirming the place still sits where it did is a
  re-reading, and nothing in this piece does it.
- **`reply_settlements`' two-word anchor vocabulary** is a different axis
  (does the judgement name a manuscript address), and nothing here
  widens it.
