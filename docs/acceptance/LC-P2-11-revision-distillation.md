# LC-P2-11 T01's second case — candidate rules from tracked changes

**What this is.** The distillation's other half: a rule distilled from the
chain's **tracked changes** rather than from its comments, and the first
batch of candidates built from the third pilot's real material.

**Why it exists.** `distil_candidate` took its cases from the chain's
comments and nothing else — a rule's case had to resolve to a comment
under an issue key. **A marked-up manuscript may hold hundreds of tracked
changes and not one comment**, and the third pilot is exactly that shape:
23 versions, 208 recorded revisions, **zero comments**. A distillation that
reads only comments has **no case at all** in such a manuscript, and a rule
distilled from nothing is not a rule.

---

## 1. The three decisions, and where each is held

| # | The decision | Held by | Witnessed by |
|---|---|---|---|
| 1 | **The key is the product's, and the caller cannot write one.** A comment's issue key is a person's judgement (ADR-0017 C10) and is given; **a revision has no such judgement to give** — a tracked change is a fact about a file whose address already names it. So the caller names the *revision* and the product mints the key | `src/labcairn/papers/chain.py`'s `revision_source_key`, `src/labcairn/guidance/distil.py`'s `distil_candidate_from_revisions` — **whose signature takes `revision_event_ids` and has no key parameter at all** | `test_the_caller_cannot_write_the_key`, `test_a_revision_case_is_bound_to_the_chain_address_and_the_key_is_the_products` |
| 2 | **The scope is the cases', assembled from the chain.** It is the **paragraph the change sits in**, read **in the change's own view** — an insertion belongs to the accepted text, a deletion to the rejected one (ADR-0014 D4a). A paragraph that could not be read is **named as unread**, never quoted as the empty string | `src/labcairn/guidance/distil.py`'s `_revision_scope_of`; `src/labcairn/papers/revisions.py`'s `read_paragraph_context` and `read_rejected_paragraph_context` | `test_the_scope_is_the_paragraph_the_change_sits_in`, `test_a_deletion_is_read_in_the_rejected_view` |
| 3 | **Who proposes is said once, in the record, and the two paths are not the same name.** The comment path's proposer is `model_proposal` — a distillation run over a corpus of comments is a model's work. **The revision path's proposer is `operator_proposal`**, because an operator reading a mentor's tracked changes is a person's work, and **the record must not claim a model did something a person did** | `src/labcairn/guidance/distil.py`'s `MODEL_PROPOSER` and `OPERATOR_PROPOSER` | `test_the_two_distillations_name_two_different_proposers`, `test_a_manuscript_with_no_comment_can_still_yield_a_candidate` |

**And the confirmation door is the same door.** A revision candidate is a
`candidate` like any other: only a second reader moves it, and the
confirmer cannot be the proposer. **The proposer not being the model does
not weaken the door** — an operator's proposal is a proposal like any
other. Witnessed by `test_the_candidate_is_not_confirmed_by_its_own_proposer`
and `test_a_second_reader_confirms_the_revision_distillation`.

### 1.1 One case or two?

**The choice made: one case per change, and a rule may cite several.**

A revision pair — a deletion and the insertion that replaced it — is
**two events in the chain**, and the chain does not say that one answers
the other: the pairing of a comment with a change is a judgement that
carries its own evidence (ADR-0017), and **no such judgement exists here
to make**. So the product does not pair them; **it gives each change its
own case, and a rule cites the changes it rests on.** The grouping into a
pair was the **operator's** reading, recorded in the run's own output — not
the product's.

**And the source key is the revision event's own id.** The revision
events' ids are already derived from the version and the element's path,
so the key is an address a reader can follow: a reader who opens the key
finds the change itself. **It is not a namespace, and nothing is decided
by its spelling** — a comment's issue key is a person's judgement and may
be spelled any way at all, so the retrieval tells the two apart **by
looking them up**, not by reading their first letters.

### 1.2 And the retrieval knows a revision source

**A rule bound to a revision is not a dead rule.** The retrieval resolves
every source against the chain at query time, and a revision's source
lives by the change itself: the chain holds it, and the reader may read
the manuscript it is in. **There is nothing left to judge** — a comment's
source lives or dies by a judgement about whether something answered it,
and a revision's source *is* the change.

**This is a second way a source can be standing, and the source state
says which it is** (`kind`: `comment` or `revision`). Without that, a
source state would be about a case nobody could look up.

---

## 2. The witnesses

`tests/test_guidance_revision_distillation.py` — 14 tests, and every one
of them was **mutation-checked**.

| The witness | What it holds |
|---|---|
| `test_a_manuscript_with_no_comment_can_still_yield_a_candidate` | the third pilot's shape — revisions and not one comment — still yields a candidate |
| `test_a_revision_case_is_bound_to_the_chain_address_and_the_key_is_the_products` | the rule is bound to the change's own address |
| `test_the_caller_cannot_write_the_key` | the entry point takes revisions, not keys; a caller cannot bind a rule to material of its own choosing |
| `test_the_scope_is_the_paragraph_the_change_sits_in` | the scope quotes the paragraph, in the accepted view for an insertion |
| `test_a_deletion_is_read_in_the_rejected_view` | a deletion's paragraph is the manuscript *as it was* |
| `test_the_example_is_the_half_that_shows_the_change_best` | a tracked change is often a fragment of a sentence, and the example must be the half that shows most |
| `test_the_example_names_the_key_of_the_case_it_shows` | the key beside the example is the example's own key |
| `test_a_paragraph_that_cannot_be_read_is_named_not_quoted` | a case with no readable context says so, and the empty string is never quoted as the reviewer's surroundings |
| `test_a_rule_with_no_case_is_refused` | no case behind a rule is refused |
| `test_a_revision_the_chain_holds_no_case_for_is_refused` | a named revision the chain holds nothing under is refused, not skipped |
| `test_the_candidate_is_not_confirmed_by_its_own_proposer` | the proposer cannot confirm their own rule |
| `test_a_second_reader_confirms_the_revision_distillation` | a person who did not propose it confirms it |
| `test_the_two_distillations_name_two_different_proposers` | `model_proposal` ≠ `operator_proposal` |
| `test_a_confirmed_rule_on_a_revision_is_served_with_its_source` | the revision source is live, and the retrieval says so |

### 2.1 The mutations, and what each one turned red

**A witness that does not fail when the property is broken is not a
witness.** Eight mutations were applied, one at a time, and each was
checked to turn the tree red:

| # | The mutation | What it turned red |
|---|---|---|
| 1 | the scope's paragraph context dropped | 9 tests |
| 2 | the rule bound to a **caller-written** key | 3 tests |
| 3 | the proposer claims to be `model_proposal` | 2 tests |
| 4 | every change read in the accepted view — **the wrong view for a deletion** | 1 test, exactly the view witness |
| 5 | the retrieval loses the revision route | 10 tests |
| 6 | a revision the chain holds no case for is **skipped** rather than refused | the refusal witness |
| 7 | the example falls back to key order — **the fragment instead of the sentence** | the example witness |
| 8 | an unreadable paragraph quoted as the **empty string** | the unread-paragraph witness |

**Mutation 7 survived its first attempt, and the reason is worth
recording.** The witness was built with the fragment's key sorting
*second*, so picking by key order happened to pick the right case and the
mutation was invisible. **The fixture was rebuilt so the fragment's key
sorts first** — which is the arrangement the real material has — and the
mutation then turned the witness red. **A witness that cannot fail is a
witness that has not been tried.**

**And mutation 8 came out of the real run, not out of a thought.** The
third pilot's mentor wrote a paragraph that is **nothing but an
insertion**, with a deletion nested inside it — Word's "inserted, then
deleted" — and **such a paragraph has no baseline at all**: there is no
manuscript before the change, so its rejected view is empty. The
implementation already named that case as unread, and **the fixture that
reproduces it did not exist until the real material asked for it.** The
real material and the witness found each other.

---

## 3. The real run — proj-pilot-3

**The material.** The owner's third pilot: the ozone/MNBs paper on
*CuSO₄-enhanced ozone micro-nano bubble disinfection of algae*, 23
versions from 2026-04-30 to 2026-10-02, 229 tracked changes of which 208
were recorded as edits, **and not one comment**. The mentor's own changes:
**nine**.

**The run.** Operator-side, outside the repository
(`E:\labcairn-local\distil_rules_pilot3_revisions.py`), against the
pilot's own workspace, with the database copied before the run wrote to
it. The output is on disk: the case set, the candidates, and the copy.

### 3.1 What came out: two candidates

| | The mechanism renamed | The clause explained |
|---|---|---|
| **Issue kind** | `language_and_format` | `language_and_format` |
| **Statement** | When the mentor replaces the mechanism a sentence names, the rule states the mechanism the mentor chose and the one it replaced. | When the mentor adds a parenthetical clause, the rule states what the clause explains. |
| **Cases** | 2 | 2 |
| **Sources** | `rv-d30278f57bec9599`, `rv-86f1b8152e74b208` | `rv-566ce379929a90a4`, `rv-a250681fef20b2c3` |
| **The mentor's own words** | 「改成铜离子的极化」/「作用，活化臭氧等」 | 「（促进溃灭后，能量集中释放，加速」/「对藻的攻击）」 |
| **State** | `candidate` | `candidate` |
| **Proposer** | `operator_proposal` | `operator_proposal` |

**Both are live.** The retrieval resolves both sources against the chain
and reports `found: True, reachable: True, addressed: True, kind:
revision` — **a rule bound to a revision is served, not merely stored.**
(Read back out of the pilot's own workspace after the run: `hits total:
3`, of which `hits carrying a revision source: 2`.)

### 3.2 What was read and deliberately not distilled: five

| The change | Why it did not become a rule |
|---|---|
| 「）」 and 「（」 | **the change carries no word — only a mark.** A rule about a bracket is not a rule about the manuscript's argument |
| 「或」 | one word with no rule in it on its own; the operator read it and found nothing a reader could be told to do differently |
| 「诱导表面氢氧根离子产生自由基的能垒的变化」 | **a deletion with no replacement.** The mentor removed a phrase without saying what should be there instead, so the change says what is wrong and not what is right — **and a rule needs the second half**. **It is also nested inside an insertion**, in a paragraph that is nothing but that insertion, so **the rejected view of the paragraph is empty** — there is no manuscript before the change to read it in |
| 「因此」 | one connective word; read, and nothing in it |

**Four of the mentor's nine changes carry no word, and one carries a
deletion without its replacement.** The run counted two candidates out of
nine changes, and the record says which five it did not use and why. **A
run that reported nine rules from nine changes would have been flattering
and wrong**, and the count is the part of this record most likely to be
quoted out of context — so it is here with the reasons attached.

### 3.3 The shape the real material has, and the chain does not

**The mentor's paragraph 4 is nothing but an insertion**, with a
deletion nested inside it — Word's "inserted, then deleted". **Such a
paragraph has no baseline at all**, so the rejected view of it is empty:
there is no manuscript that existed before the change.

**And that is not a defect in the reading — it is a fact about the
material.** A mentor who writes a paragraph from scratch and then
deletes two words inside it has left the chain holding a change whose
"before" was never a manuscript. **The scope says the paragraph could
not be read**, and the change's own words are still the example. **A rule
distilled from that change rests on a case whose context does not
exist**, and the record of the distillation says so rather than quoting
an empty string as though it were the reviewer's surroundings.

---

## 4. The honest limits

**These two candidates are thin, and the record says so.**

1. **Each rests on one group of changes — two cases.** **One group is not
   a rule that has been confirmed; it is a proposal that a second reader
   has to look at.** Neither candidate has been confirmed, and nothing in
   this run moves them: the confirmation door is the same door, and the
   confirmer cannot be the proposer.
2. **Both are at the wording level, not the methodological level.** The
   mentor's tracked changes in this manuscript are edits to *sentences* —
   a term renamed, a clause added. **Nothing here says anything about the
   method, the data or the statistics**, and a reader who served these two
   rules to a student would get *wording* advice and nothing more. **The
   third pilot's mentor did not revise the argument in the margins because
   there were no margins** — the tracked changes are what was there.
3. **The two candidates are the same kind of rule.** Both are
   `language_and_format`. **Two rules of one kind resting on one case each
   is not a pattern** — it is two proposals that may or may not be the
   same rule written twice.
4. **The grouping is the operator's judgement, and the product does not
   make it.** The product gave each change its own case and its own key.
   **Which changes belong to one rule is a reading a person made**, and it
   is recorded in the run's output as the operator's, not as the product's.
5. **The mentor's nine changes are nine changes in one version of one
   draft.** They are not a cross-version pattern, and **a rule that holds
   on one paragraph of one draft has not been shown to hold anywhere else.**
6. **The deletion without a replacement is the interesting negative case,
   and it is not solved.** The chain records what was removed and not what
   the mentor wanted instead — **which is exactly the missing half of the
   rule**, and no amount of reading the tracked change recovers it. **This
   is the seam the third pilot exposes**: a mentor who revises without
   writing leaves the chain holding the "before" and no "after".
7. **Nothing was measured on a runner.** The shard cost for the new test
   file is **apportioned**, not measured: the local whole-file cost
   (10.21 s on Windows) scaled by the platform ratio the record already
   holds (`ubuntu = 0.473 × windows`), which is the same two-step the
   LC-P2-09 record used. **The next CI run replaces it with a
   measurement.**

---

## 5. What was not done

- **No second reader was found, and none was simulated.** The candidates
  are `candidate`, and the confirmation door was exercised only by the
  witnesses.
- **The comment path was not changed.** `distil_candidate` and
  `MODEL_PROPOSER` are as they were; the two paths share the rule
  lifecycle, the retrieval and the vocabulary, and nothing else.
- **No schema change.** `guidance_rule_sources.issue_key` holds both
  kinds of key, and the chain tells them apart by looking them up.
- **No rule was proposed from the student's 159 changes or the model's
  40.** The pilot's own roster records the student's edits and the model's
  marks, and **a rule distilled from a model's own edit is a rule with no
  advisor behind it** — which is a separate question and was not asked
  here.
- **The chain's second ring was not filled for the third pilot's
  material.** The `edit_actions` rows carry no `feedback_id`, because
  there is no comment for a change to answer, so **a revision source has
  no "was this answered" judgement** — and the retrieval's revision route
  does not ask for one, because a revision source *is* the change.
