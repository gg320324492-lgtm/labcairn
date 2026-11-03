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
6. **The deletion without a replacement was the interesting negative case,
   and §6 recovers it.** The chain records what was removed and not what
   the mentor wanted instead — **which is exactly the missing half of the
   rule**, and no amount of reading *one* tracked change recovers it.
   **What recovered it was reading the change beside its neighbours**: the
   deletion and the insertion that replaced it are two fragments of one
   edit, and a run that groups by fragment cannot see the edit. The seam
   the third pilot exposes is real — a mentor who revises without writing
   leaves the chain holding the "before" — but the "after" was in the
   chain all along, in a different row.
7. **Nothing was measured on a runner, and the cost in the table is not
   the one this record first described.** The shard tool does not scale a
   local number by a platform ratio: `remeasure_shards.py` reads the
   per-file seconds out of a run's `--durations=0` log and **divides the
   unaccounted residual among the files the run never saw, by test count**,
   saying so in its own output ("the 35 fast files share 31 s"). At
   `3d1487e` the revision-distillation file therefore carries an
   apportioned 0.92 s (ubuntu) and 1.66 s (windows) against **14.9 s
   measured locally on Windows**.

   **That next run has happened, and it replaced them.** Run
   `41566766491` (head `bb8f8f6`) measures the file at **7.16 s (ubuntu)
   and 86.18 s (windows)**, committed at `69a3bd5`. **The apportionment was
   low by about fifty-two times on Windows** — LC-P2-06 recorded nine times
   for its file, so the direction of that lesson held and its size did not.
   What is still apportioned in the table is the set the tool names in its
   own output (36 fast files sharing 33 s on ubuntu, 28 sharing 35 s on
   Windows): files too quick to appear in the durations section. None of
   them decides a shard's length.

   **And one number moved the other way.** `test_cli.py` got a cheaper test
   in `f8dbbe8` — a five-minute fixture became a four-second one — and its
   measured cost still rose, 330.81 → 380.28 s (ubuntu) and 765.32 → 824.96
   s (windows), because the same batch added a witness to that file. **A
   file that gets a cheaper test does not necessarily get cheaper.**

---

## 5. What was not done

- **No second reader was found at the time, and none was simulated.** The
  candidates stayed `candidate` and the confirmation door was exercised
  only by the witnesses. **A second reader arrived afterwards** — see §6,
  which is the second pass over these same two rules.
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

## 6. The second pass: the two rules were re-read, and one door was added

**This section is the record of what happened to the two candidates after
§3, on 2026-11-03.** It changes nothing in §3's description of the first
run — the first run did what §3 says — but §3's outcome did not survive a
second reading, and a record that stops at the flattering half is not a
record.

### 6.1 What was wrong, and what caused it

**Both statements described a rule instead of stating one.** "When the
mentor replaces the mechanism a sentence names, the rule states the
mechanism the mentor chose and the one it replaced" says nothing about a
manuscript: it says what a rule would contain. **A reader holding the
draft learns no standard from it.**

**The cause was the grouping, and it is worth naming precisely because it
is reproducible.** The first run grouped the mentor's changes by *which
fragment of text each one carried*. One edit — a mechanism replaced by
another — arrived in the file as several tracked changes: the phrase
deleted, the connective "or" deleted, and the replacement written in as
two insertions (Word records what a writer typed at two moments as two
events). Split that way, each fragment looks like a separate act, and
**an operator who cannot see the act writes about the fragment**. That is
how a circular statement gets written: it is what is left to say about a
piece of a sentence.

**So the grouping was redone by act, not by fragment**, and the two groups
grew: the mechanism rule went from 2 sources to 4 (it now carries the
deletion and the connective as parts of the same act), and the
causal-chain rule keeps its 2. **The brackets are deliberately outside
both groups** — they are the punctuation of the replacement, and a bracket
is not a case any statement could be learned from.

### 6.2 The door the product did not have

**Fixing a thin rule needed a product capability, not a hand-written
record.** Two ways existed and both were wrong:

- `distil_candidate_from_revisions` mints a **new** rule id every time, so
  the corrected rule would have stood beside the thin one and the memory
  would hold two answers to one question.
- `supersede_rule` keeps the id but takes `scope` and `example` **from the
  caller** — and the whole reason the revision path exists is that a
  caller must not write a scope. Using it would have meant hand-copying
  what the product computes, which is the door this module was built to
  keep shut.

**`distil_revision_version_of` is that door**: the rule keeps its id, the
version increments, the scope and the example are built from the cases
exactly as on the first version, the proposer is still
`operator_proposal`, and **the new version starts as a candidate — a
rewording is not a confirmation**.

**And disputing alone would not have been enough, which is the part the
retrieval decides.** `search_rules` serves `confirmed` **and** `disputed`
rules by default, so a disputed empty statement **keeps reaching readers'
cards**, carrying its reason beside it. The pair that actually removes it
from service is dispute **plus** a new version: `read_guidance_rules`
returns only the highest version, so once the candidate v2 exists, the
disputed v1 is no longer what a query answers with — and v2 is itself not
served until a person confirms it.

**Seven witnesses**, and four mutations measured against them: minting a
fresh rule id fails 3; not reading the old rule fails 7; taking the scope
from the rule rather than the cases fails 18; not incrementing the version
fails 5.

### 6.3 The example showed the words the mentor rejected

**A defect in the product, found by the second pass and not by the
witnesses that were already there.** `_revision_example_of` picks the
**longest** change among the cases — right when one insertion is split in
two, because the longer half is the fuller one. It is wrong when an edit
*replaces* a phrase: the mentor deleted a twenty-character mechanism and
wrote an eight-character one in its place, so the longest case was the
deletion, **and the rule telling a reader what to write was illustrated
by the words the reader is being told not to write**.

**An insertion is now chosen before a deletion, whatever their lengths**,
and length decides only among insertions. One witness builds the shape
deliberately (a deletion longer than the insertion) and asserts both
halves: the example must carry the written words, and must not carry the
removed phrase. Dropping the insertion preference turns that witness red
and no other.

### 6.4 What the second reader decided

**The owner read both statements and confirmed both**, as `confirmed_by =
"owner"` — **not** `operator_proposal`, because the proposer cannot
confirm their own rule and the run that wrote them was the proposer. Both
rows are `confirmed` at version 2, and a query on the issue type serves
them with all their sources standing.

**The issue kind moved from `language_and_format` to
`method_and_hypothesis`.** The first run's label was a misreading of its
own axis: the vocabulary names *what problem the advisor pointed at*, not
*what transformation of the text was made*, and a mentor replacing one
chemical mechanism with another is pointing at the method as described.
The old label stays on the disputed version 1, which is what the memory
keeping its past looks like in a row.

### 6.5 What this still does not show

- **Two rules, each resting on one act, in one paragraph of one draft.**
  §4's objection stands in full: this is not a pattern, and re-reading the
  acts does not manufacture cases that were never there.
- **The statements name this paper's chemistry.** They are usable by a
  reader of *this* group's manuscripts and are not a general writing
  standard. That is what the memory holds a rule to be — one advisor's
  standard, traceable to the moment it was learned — but it means these
  two will not transfer to a different subject.
- **A check is now bound to each rule, at version 2 — closed 2026-11-03.**
  A rule may name the question a reader runs against a manuscript and what
  answers it, and each of these two now does:
  `rule-1fcc9d1a2573d7b0` v2 names `check-a1de7d4db9d7cbda` and
  `rule-1006b8ca1120db13` v2 names `check-5df4997384d6a0bd`, both confirmed
  by the owner as a second reader and read back through `read_rule_checks`
  onto the retrieval card. [`LC-P2-11-check-binding.md`](LC-P2-11-check-binding.md)
  is that record. **What the closure does not change is the objection
  above**: each check rests on one act, in one paragraph of one draft, and
  **neither criterion has been observed to *not* fire** — the material holds
  no sample where the mentor left a parallel set of mechanisms, or a bare
  「促进」, alone. So both criteria are read out of what the mentor *did*,
  and are untested against what the mentor left be.
- **One number in those rows is not a time.** Both checks carry
  `proposed_at = confirmed_at = 2026-11-03T18:00:00+00:00`, chosen as a
  fixed instant so a re-run of the same proposal is the same row — but the
  write happened at **05:07 UTC**, so the stored instant is about twelve and
  a half hours **after** the event it dates. The state machine is unaffected
  and the row is idempotent, **yet a reader who takes the column as a
  timestamp is being shown a moment that had not arrived**. It is left as it
  is because the memory does not rewrite its past; it is named here because
  that rule is no licence to leave a misleading value unmarked.
- **The new witnesses were not measured on a runner when this section was
  written**; §4 item 7 carries the measurement that has since arrived, and
  §7 carries the whole-suite run this branch was checked with.

---

**And §6's second pass was run through the product's own doors.** The
dispute, the new version and the confirmation each went through
`dispute_rule`, `distil_revision_version_of` and `confirm_rule`; the
operator's script names the acts and the statements and nothing else, and
**it does not build a scope, a key or a state**. That is the property the
whole module exists for, and the second pass is the first time a real
corpus exercised it end to end: read, propose, dispute, rewrite,
confirm — five acts, four of them the memory's own.

---

## 7. The whole suite, and a claim about it that did not survive re-measurement

**Why this section exists twice over.** The window that landed §1–§4 wrote a
measurement section of its own — **4665 passed, 5 failed, 5 skipped** — and
argued the five failures were not its work's: the two witnesses that clone a
repository and build a wheel, it said, **were already red at the commit the
branch starts from**. That commit never reached this branch: `git cherry`
reports its patch as not upstream, and the string it measured does not appear
anywhere in `docs/`. **So the record was missing, and what was missing of it
was a claim this tree contradicts.** Landing it as written would have carried
an excuse forward for failures that are not here.

**The whole suite at `69a3bd5`, this machine, 2026-11-03:**

| | |
|---|---|
| Result | **4739 passed, 0 failed, 14 skipped** · 33m21s |
| Test count against the earlier record | 4665 → 4739 — the delta is additions (§2, §6's witnesses and the ceiling pair), and the witness ledger over `ba80a28..bb8f8f6` reports **LOST — none**, so nothing was renamed away |
| The named skips | POSIX permission bits, POSIX path semantics, the 8.3 short-name cases on a volume that has none, and the provider smoke that **refuses to run without the owner's authorisation to spend money** |

**And the base-commit check, run under the same conditions.** The five
witnesses the earlier record excused were run at `e13b967` — the commit this
branch starts from — in a separate worktree, with no `PYTHONPATH` injection
(the injection is what makes a worktree run measure somebody else's code, and
it also breaks the wheel test's clean venv): **18 passed, 0 failed**, 2m21s.

**So the claim does not hold here, and it is not carried.** Whatever made those
five red on that tree at that hour — the worktrees and caches on this machine
were in a different state then — the same witnesses are green at the base
commit and green at this head. **A sentence that reads *"not our failure, it
was already red"* is only worth writing when the parent tree has been measured
under the same conditions; measuring it reversed the conclusion.** That is the
method this project keeps paying for (§4 item 7's apportionment reversed by
fifty-two times is the other one), and it is why the number lives here with its
commit rather than in a commit message.

**What this does not establish.** One machine, one platform. The shard
partition is balanced on runner seconds, and §4 item 7's are the only ones
this section quotes as measured — a development-machine total is not evidence
about the runner, only about this machine.

---

**A fourth pilot has since been run on the same door, at a hundred times the
size**: a submission's six drafts and five marked-up copies, **897 tracked
changes by one reviewer**, from which seven groups were read and six confirmed
— and the same reviewer's standards compared against the second corpus's.
[`LC-P2-11-pilot-4-distillation.md`](LC-P2-11-pilot-4-distillation.md). **What
did not change is the door**: no new shape, no new parameter, and one
single-act rule left as a candidate rather than dressed as a standard.
