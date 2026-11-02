# LC-P2-07 — the revision event's identity, per change rather than per path

**What this record is.** It closes the one assumption
`docs/acceptance/LC-P2-09-acceptance.md` §9.6 named and left standing — *the
element's path is unique inside a part*, the claim the revision event's id
rested on — and it is **not** a restatement of the double-read that
`docs/acceptance/LC-P2-07-fidelity-baseline.md` §5.6 already records as fixed
by `f4a7e94`. That §5.6 measured 239 events against 239 distinct addresses;
this record re-confirms it and then deals with what §5.6 explicitly deferred:
the identity itself, which assumed path-uniqueness as a fact about OOXML when
it is only a fact about one reader's scan. A reader is code, and the id should
not rest on the scan staying narrow. Every number here is re-measured against
the tree this work lands on — `docs/debt-closures` at `0a8b6e6` plus the
commits that follow — not carried forward.

## 1. The two records that named this, and what changed since

`docs/RELEASE-NOTES.md` §2.22 and `docs/acceptance/LC-P2-09-acceptance.md`
§9.6 both state the same defect: the reader reports **243 changes where the
file holds 239**, one change recorded twice in one file, and the id rests on
an assumption — *the element's path is unique inside a part* — that is
**false as written**, holding only because the four duplicates happen to be
the same change; two *different* changes sharing a path would lose one
silently.

**The double-read itself is already fixed.** Commit `f4a7e94` ("the reader
reports one tracked change once, not twice") removed it: the outer
paragraph's walk no longer crosses into a drawing's text box to report the
box's revisions a second time. **Re-measured on this tree**, the file that
produced the 243 — `corpus-1-mn-bubbles/versions-chinese/v04b-variant-2-copy-chinese-draft.docx`
— now reads **239 events against 239 distinct element paths and zero
duplicated paths**. The 243/239 symptom no longer reproduces here; it is a
statement about the pre-`f4a7e94` reader.

**The identity defect is not.** What `f4a7e94` fixed was the *reader*
producing one element twice. The claim the id rests on is a separate thing,
and it is still false as written.

## 2. Whether the assumption is true, measured

The id is `sha256(version_id, part, element_path)`. Its docstring asserted
the path is unique inside a part. Two measurements, one on the real material
and one constructed:

**Over the real material there is no collision.** The 23 third-pilot drafts
(`materials-library/gxw-ozone-mnbs-2026-11/entries/entry-NN.docx`) read
**229 direct tracked-change elements = 229 reader events = 229 distinct
element paths**, zero shared. Over the 18 corpus-1 `.docx` files the only
count that disagrees is `v06b-variant-2` (**223 direct, 222 read**) and that
is the *opposite* defect — a row-insertion marker in `w:trPr`, outside any
paragraph, that the paragraph-only scan never reports. It is a loss, not a
duplication, and it is recorded separately in the fidelity baseline §5.6.
No real file put two different elements on one path.

**The path function is not injective in general.** `_element_path` names a
step by the element's **local** tag and counts its index among siblings that
share the **full** namespace-qualified tag. A `w:ins` and a foreign `o:ins`
as siblings therefore both render as `ins[1]` on the same path. The reader
reports only `{W}ins`, so this cannot reach `record_revision_events` *today*
— it is a latent collision, reachable the moment the reported set widens (a
footnotes part, a cross-namespace move pairing, a second view). The id should
not rest on the reported set staying narrow.

**So the assumption is false as written and true only by the reader's
accident.** A property stated and not watched is not held; here it was
watched only for the case the reader could produce, never for the case the
identity actually needs.

## 3. The fix: an occurrence, with the first change byte-stable

`_revision_event_id` now takes an `occurrence` — how many changes the same
`(part, element_path)` has already been given in this document, counted in
the document's own order. The **first** change at an address is
`occurrence == 0` and that path hashes `version|part|path` with **no suffix
at all** — byte-for-byte the id every stored row already carries. Only a
second and further change at one address get `\x00occN` and so a distinct id.
`record_revision_events` counts the occurrence from `document.revisions`
(the reader's top-to-bottom order), so re-reading the same bytes gives the
same number to the same change and the same ids: the identity is a function
of the manuscript, never of the caller's arrangement or the wall clock.

**Why not fold the text into the id.** Hashing the change's own text would
make a collision distinguishable but would move **every** id — and the id is
the key guidance rules are bound to (§4). The occurrence moves no id at the
first change and pays a suffix only where two changes genuinely share an
address.

## 4. The blast radius, measured before writing it

A revision event id is not internal: it is the key `guidance_rule_sources.issue_key`
binds to, and the chain's `edit_actions` are keyed off it. The pilot's
`revision_events` (read-only, **not touched**) holds **2164 rows / 2164
distinct ids**, and grouping by `(version, part, element_path)` gives **zero
groups larger than one** — so every stored row is the first change at its
address, `occurrence == 0`.

Re-deriving all 2164 ids with the new default-`0` formula gives **0
mismatches**: no stored id moves, and no binding is re-pointed. The two rules
the owner confirmed as a second reader on 2026-11-03 — `rule-1fcc9d1a2573d7b0`
and `rule-1006b8ca1120db13` — bind through `guidance_rule_sources.issue_key`
to `rv-…` ids that resolve one-to-one to real `revision_events` rows; every
one of those keys is an occurrence-0 id, so all of them survive the change
unchanged. `edit_action_id_for` prefixes the event id it is handed and derives
nothing of its own, so the same stability reaches the `edit_actions` rows.

The pilot database was opened read-only throughout and no row was rewritten.

## 5. The snapshot rule, stated

The chain's rows are a snapshot written by the reader that was running at
ingest time, so changing the reader does not retroactively touch the 2164
rows. **This is not a problem here, and it is important to say which way.**
The fix does not claim the stored rows were wrong — they were not: the real
material has no collision (§2), and every stored row is occurrence 0 with the
identical id. The fix hardens the identity against a collision the reader
does not currently produce. **No correction to the pilot database is owed,
and none was made.** The separate, still-open loss `v06b` (the unreported
row-level marker) is unchanged by this work and remains recorded in the
fidelity baseline.

## 6. The witnesses, and the mutations that check them

All in the reader's own test file (`tests/test_ooxml_revisions.py`) and the
writer's (`tests/test_version_store.py`); no new test file, so no shard cost
to re-measure. The private `_revision_event_id` is imported because the
witness is about it. The collision itself is driven at the seam the identity
is decided — the rows the writer builds, with `read_document` replaced by a
two-event document — because the real reader will not mis-address a document
(§2), and a witness that only checks the reader would be checking the wrong
thing.

| Witness | The property | Fails when |
|---|---|---|
| `test_the_revision_event_id_carries_an_occurrence_per_change_at_one_address` | (a) occurrence 0 equals the legacy digest exactly; (b) occurrences 0/1/2 give three distinct ids | the digest drops the occurrence (b), or folds it in unconditionally (a) |
| `test_the_revision_event_id_is_re_derivable_not_position_dependent` | the same `(version, part, path, occurrence)` gives the same id every time | the digest mixes in a clock or a per-call counter |
| `test_two_different_changes_on_one_element_path_are_recorded_as_two_events` | two changes at one address with different text → two rows, distinct ids, and re-record is the same two rows | occurrence ignored: they collide on one id and the writer raises `ANCHOR_STALE`, recording neither |
| `test_two_changes_on_one_path_that_share_their_text_are_still_two_events` | two changes at one address with **identical** text → still two rows | occurrence ignored: the replay branch matches the text and silently drops the second |
| `test_a_stale_anchor_is_still_refused_on_an_occurrence_bearing_id` | the collision and the drift are decided apart: a collision is recorded as two events, a drift on an *occurrence-bearing* id is still refused as `ANCHOR_STALE` | an occurrence that is not re-derived on re-read, or a writer that skips a text-mismatched occurrence-bearing row instead of calling it stale |

The existing `test_the_derived_revision_event_id_names_one_change_per_address`
stays green and is *not* the witness for this defect: over the corpus every
address is unique, so it only ever exercises occurrence 0 — which is exactly
why it never covered a collision. The new witnesses cover the case that test
structurally cannot reach.

**Mutation 1 — `_revision_event_id` ignores the occurrence (the pre-fix
defect restored).** Three went red: the unit witness's distinct-ids half
(`{id0, id1, id2}` collapses to one), the different-text writer witness (one
id → replay check finds the first row → `ANCHOR_STALE` → neither recorded),
and the same-text writer witness (text hashes match → the second is silently
`continue`d → one row where two changes are). The corpus witness stayed green,
as expected — it cannot see a collision it never generates.

**Mutation 2 — fold the occurrence in unconditionally, with no `if`.** The
unit witness's *first half* went red (`_revision_event_id(v, part, path)` no
longer equals the legacy digest), and re-deriving all 2164 pilot ids against
that mutant moves **every one of them** — the precise number that makes the
`occurrence == 0 → no suffix` rule load-bearing for not orphaning the live
rule bindings.

**Mutation 3 — the writer forces `occurrence = 0` (the digest left intact).**
This is the mutation the work order asked for specifically — *an occurrence
that is always zero*. All three writer witnesses went red, and the failure is
the mislabel named in §5: the different-text pair and the drift-on-occurrence
pair are both refused as `chain_anchor_stale` (measured id `rv-73506d9c5e31a27a`
on the marked-up fixture), reporting a collision as if the bytes had drifted,
and the same-text pair folds to one row. The unit witnesses stayed green —
they call `_revision_event_id` directly, where the `occ` argument still works;
it is the writer not *passing* it that this mutation tests. Together Mutations
1 and 3 bracket the two places the identity could fail: the digest, and the
count handed to it.

## 7. There is no separate "collision" refusal, and that is the fix

The work order asked whether a same-address collision should carry its own
named refusal, distinct from `ANCHOR_STALE`. Measured on the fixed tree, the
answer is that it should **not**, for two reasons, and both are checked.

**A collision is no longer a refusal at all.** The two changes at one address
get different occurrences, so different ids, and both land as rows
(`test_two_different_changes_on_one_element_path_are_recorded_as_two_events`).
Refusing them -- even with a well-named reason -- would drop a change, which
is the very loss this work removes. The collision-versus-drift distinction is
therefore decided by *outcome*, not by label: a collision is recorded, a drift
is refused, and `test_a_stale_anchor_is_still_refused_on_an_occurrence_bearing_id`
holds the two apart on an id that carries an occurrence. `ANCHOR_STALE` now
fires **only** when a row already in the store disagrees with what the same
address re-reads -- genuine drift -- never on a within-file collision.

**A new enum could not be witnessed and is out of the file map.** `ChainRefusal`
lives in `chain.py`, but every member must be mapped in
`application/refusal.py` (`CHAIN_REFUSALS`) or
`test_feedback_events.py::test_every_chain_refusal_has_a_layer_name` goes red --
both outside the files this work order owns. An unreachable reason would be
dead code that violates the project's own rule that a claim stated and not
watched is not held. So the collision is closed by construction (the occurrence)
and witnessed by the outcome, and the drift guard stays named and reachable.

*Anchored to:* `docs/debt-closures` @ `0a8b6e6` (the tree this was measured
on after a clean fast-forward merge into the working branch). The 2164-row
re-derivation was run read-only against
`E:\labcairn-local\pilot-ws\labcairn.db`; the file counts against
`E:\labcairn-local\materials-library\`. The `w:trPr/w:ins` row-marker gap
(`v06b`, 223 direct against 222 read) is already named on the tree in
`LC-P2-07-fidelity-baseline.md` §5.6 ("one defect this work found and did not
fix"); this record cites it rather than re-adding it.
