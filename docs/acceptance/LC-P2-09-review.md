# LC-P2-09 — independent review of the feedback-chain acceptance record

**Record reviewed:** `docs/acceptance/LC-P2-09-acceptance.md` — the four
chain tables and their wiring (§1-§5), the reply (§6), the middle rings
(§8), the rings filled on the pilot's own workspace (§9), and the
settlement over a reply (§10) — as it stands in this branch.
**The tree reviewed:** `e10359e`, the branch tip this review worked in.
**Platform:** Windows 11 (10.0.26300) AMD64.
**Interpreter:** the repository's virtualenv at `E:\LabCairn\.venv` (CPython
3.12) with `PYTHONPATH` pointed at this worktree's `src/` — `import labcairn`
verified to resolve to this worktree before any run. Each run had its own
`--basetemp` under `E:\labcairn-local\tmp`.

**Method.** Every mutation the record's four tables name was re-applied one
at a time — §4's six, §6.3's eleven, §8.4's thirteen plus the four guards of
its second pass plus the four mutations of the 2026-11-01 ruling, §9.5's one,
and §10.2's eight: **forty-three in all**. Each mutation's diff was read
before its witness ran, and the file was restored with `git checkout --`
after, with `git status` checked clean. Mutation §8.4-10 was applied the way
the record says it was applied — an in-memory patch of
`labcairn.guidance.retrieval.LIVING_STATES` from a pytest plugin outside the
tree, the file itself never edited. Two applications that did not take (an
anchor that matched two functions; a mutation whose red came from an
`AttributeError` rather than from the property) were redone in a form that
provably reached the code before anything was believed.

## 1. Baseline

`tests/test_feedback_events.py`, `tests/test_edit_actions.py`,
`tests/test_response_links.py`, `tests/test_guidance_retrieval.py`,
`tests/test_feedback_demo.py`, `tests/test_feedback_event_stream.py` —
**111 passed**.

## 2. What was re-applied, and what happened

**§4 — the wiring (6 mutations).** All six reddened the witness their row
names: the evidence rule short-circuited (`test_a_response_state_needs_a_decision_and_its_evidence`,
which the record says goes red *through the schema* — reproduced, and it
did), the pending refusal removed from the payload (`DID NOT RAISE
ValidationError`), the anchored text emptied, `change_accepted` admitted as
an assessment basis (again through the schema's CHECK), `list_unaddressed`
dropping the unanswered comment, and `record_edit` emitting no event
(`test_the_feedback_demo_runs`, "an edit event is in the stream").

**§6.3 — the reply (11 mutations).** All eleven reddened their witnesses:
both-halves CHECK removed from *model and migration together* (parity held,
the raw-`INSERT` witness went red), two-parties CHECK removed, the party
vocabulary widened, the objection no longer taken from the document (both
witnesses red), the layer read ignoring the versions named (the mutation
lives at the application layer's `read_replies`, not `list_replies` — the
witness goes through the former), the drift check removed, the verdict
column added (both layers, column-set witness red), a comment written beside
the reply, the paragraph-range check removed, the duplicate-exchange check
removed, and the answer paragraph dropped from the ordering.

**§8.4 — the middle rings (13 + 4 + 4).** All thirteen reddened their
witnesses, including the two the record flags as going red through the
database. The four guards of the second pass (edge arrives at the version;
edge of the change's own project; version belongs to the project; comment of
that project) each reddened exactly its own witness. The four ruling
mutations (the retrieval reading only the latest judgement; a withdrawn rule
served again; a candidate served without a second reader; the judgement
state never read) each reddened
`test_a_judgement_on_the_chain_is_a_fact_and_a_wrong_one_is_corrected_on_the_rule`.

**§9.5 — the listing order (1 mutation).** Putting the old order back
(`pending` checked before the judgement) reddened
`test_a_judged_comment_is_listed_as_judged_and_not_as_waiting`.

**§10.2 — the settlement door (8 mutations).** Seven reddened their
witnesses: the claim-findability check answering "nothing missing", the
judgement-discipline block short-circuited (the witness got the
`IntegrityError` the record predicts, not the door's refusal), the unsettled
listing dropping `pending`, the resolved address's range check
short-circuited, the chain-side join keeping only the newest link's state,
the already-decided check short-circuited, and the address CHECK deleted
from model and migration together (the raw-`INSERT` witness red, parity
green). **The eighth survived, exactly as the record reports**: the
operation-layer `held`-reason check short-circuited leaves every hold
witness green because the schema's
`reply_settlements_a_hold_names_what_it_holds` refuses the row instead — the
record's "recorded rather than counted" is the honest form, and this review
confirms the schema CHECK is there and fires.

## 3. What was checked against the tree, not against the tests

- **The reply's shape is the record's column set.** The witness asserting
  `ReplyRow` carries exactly the thirteen record columns (no state, no
  decider, no evidence) passes on this tree, and mutations 7 and 8 prove it
  bites in both directions.
- **The four paragraphs the reply witnesses read are in the test file.**
  The record says the repository is public and the paper is the owner's, so
  the witnesses' words are written in `tests/test_feedback_events.py`
  rather than taken from the material — verified: the letter texts live
  there.
- **Migrations `0019_replies.py` and `0020_reply_settlements.py` exist and
  carry the CHECKs the mutations target**, including
  `replies_both_halves_are_present`, `replies_the_two_halves_are_two_parties`,
  `reply_settlements_an_address_is_a_value_not_a_guess`, and the hold-reason
  CHECK that made mutation 8 a survivor.

## 4. What could not be checked, and why

**§9 is a claim about the owner's pilot workspace** — a database outside
this repository. Its counts cannot be re-measured here and are not passed
silently:

- the row counts of §9.1 (80 feedback events, 1528 revision events, 1439
  edit actions, 32 response links split 2/8/22, 16 rules, 32 sources);
- the 89 `empty_marker` changes excluded from the second ring (§9.2);
- the 22 correspondences put forward and the owner's ten judgements — two
  `addressed`, eight `not_addressed` (§9.3), including the two named issue
  keys;
- the memory's service claims (§9.4): `rule-6cc14b60015b7945` served as the
  one of sixteen, the other fifteen reported with reasons, and the second
  paper's fourteen sources contributing no candidate;
- the eight judged comments the pre-fix listing called pending (§9.5);
- the reader's 243-against-239 double-read on the fourth version (§9.6),
  which is LC-P2-07's §5.6 defect seen from the chain's side — the *code*
  claim there is checkable and was checked in this tree's own records, but
  the pilot's numbers are not.

What the tree *does* hold for §9 is the machinery those claims rest on:
every operation the section names (`record_edits_from_revisions`, the
proposal pass, `settle_reply`, the two listings, the retrieval) is in this
tree, and every one of its guards was mutation-proven above.

## 5. Findings

1. **(Note) One ruling mutation is spelling-sensitive.** "The fixture's
   judgement state ignored", applied as `addressed = True`, leaves the
   ruling witness green — the witness's every step has the source standing
   or the rule gated at the rule-state layer, so forcing all sources
   addressed changes no assertion. The form that reddens it is the
   judgement states never being read at all (`states = ()`), which fails
   the witness's first assertion. A re-applier spelling it the first way
   will report a survivor where the record reports a red.
2. No witness stayed green under a mutation that reached it, other than the
   one survivor the record itself reports (§10.2 mutation 8) — and that
   survivor is the *point* of its row: the schema holds the line the door
   states.
3. The record's §7 "what is left for the reviewer" list (the settlement not
   replayable from the stream; a reply's grade not correctable in place; a
   reply's objection not the chain's comment) matches what the code shows;
   each is stated in the record as a limit rather than claimed as a
   property.

## 6. Verdict

**Holds.** Forty-three mutations re-applied; forty-two reddened exactly the
witnesses their rows name, and the one survivor is the record's own,
reported as a survivor with the mechanism (the schema CHECK) verified
present and firing. The pilot-workspace counts of §9 are outside this
review's reach and the record does not pretend otherwise; the machinery
behind every one of those counts is in this tree and is witnessed.
