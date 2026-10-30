# LC-P2-10 — Process annotation and the gold set — task breakdown

**Work order:** LC-P2-10 (process annotation and the gold set) · **Status:**
drafted 2026-10-30; **T00–T06 landed on 2026-10-30** on the branch
`claude/p2-lc-p2-10-plans`. **T06 was two independent sessions' work and an
arbiter's, not two people's** — the manifest in the tree carries both
readings and the arbiter's row, and the acceptance record says what that
means for the agreement number. **Priority:** the adjustment of 2026-10-30
(P2-AMD-01) keeps it in step 3, between LC-P2-09 and LC-P2-11, and it is
**the one that cannot be parallelised**: it needs two independent readings
and an arbiter, and it needs the pilot corpus.

## 0. How to read this document

**This is a contract, and half of it is a reading.** §4 names the
acceptance clauses and, for each, the thing that carries it. **Four of them
are code and can be dispatched; three of them are somebody reading
manuscripts**, and a task breakdown that pretended otherwise would be a
breakdown that ships an empty gold set. **As of 2026-10-30 the readings
were made by independent Claude sessions rather than by people** — §T06 says
what changed and what did not.

**The labels are Phase 2's own.** The upstream study (`docs/research/
upstream-study/arXivEdits.md`) says why an imported taxonomy does not work:
its classes describe *what kind of text edit was made*, which is a different
axis from *what problem the advisor pointed at*. A gold set labelled with
somebody else's classes measures somebody else's task.

## 1. Goals and boundaries

### 1.1 What LC-P2-10 must produce

| | |
|---|---|
| **A label set** | The closed vocabulary an annotator chooses from, and it is LC-P2-09's own: the issue kind, the response state, and the assessment outcome |
| **An annotation guide** | What each label means, when `UNKNOWN` is the honest answer, and the worked examples that make the boundary visible |
| **A gold set** | A small, synthetic corpus with **two independent annotations per item and an arbiter's resolution**, committed with its manifest |
| **An agreement report** | Inter-annotator agreement, **with the denominator it was computed over** |
| **A partition** | The split is by `PaperProject`, never by event — every version of one paper is in one partition |

### 1.2 Already done — removed from scope

- **The chain the labels are about.** LC-P2-09's four tables, its
  `issue_key`, its response states, and its assessment outcomes are the
  vocabulary this work order labels against; **they are not redefined here**.
- **The reader.** LC-P2-07's DOCX reader produces the comments and their two
  addresses, and its fidelity baseline is the measurement this corpus inherits.
- **The version graph.** LC-P2-08's contracts and LC-P2-09's writer.

### 1.3 Explicitly not in scope

- **An automatic labeller.** The label is a person's judgement; a model's
  label is a candidate, and LC-P2-12 owns the route that produces one.
- **The pilot corpus.** LC-P2-10's corpus is **synthetic and small**, for the
  reason LC-P2-06's is: a fixture that pretends to be a manuscript is a
  fixture that tests the fixture. The pilot's real material is the owner's
  decision (P2-AMD-01 §5, item 3).
- **The guidance rules.** LC-P2-11 reads this gold set; it does not live here.
- **Inter-annotator agreement as a target.** This work order reports the
  number; it does not require the annotators to reach one.

## 2. The decisions that shape it

### 2.1 `UNKNOWN` is a label, and it is not a failure

A comment whose anchor does not pair, an assessment whose evidence is
insufficient, a response nobody made: each has an honest answer that is
neither "addressed" nor "not addressed". **`UNKNOWN` is the annotator's
answer to those**, and it is scored as an answer rather than as a missing
value. A gold set that cannot say "we do not know" is a gold set that forces
a guess, and a guess is what the chain exists to refuse.

### 2.2 The two addresses are labelled separately

LC-P2-09's first clause is that a comment has **two** addresses: the comment
element in the comments part, and the body-side paragraph and offsets. An
annotator labels **both**, and a guide that asks for one label per comment
loses the distinction the chain was built to keep.

### 2.3 The split is by `PaperProject`, never by event

**Two versions of one paper are two observations of one thing.** A random
split by row would put version 1 in training and version 2 in test, and a
system that memorised version 1 would score on version 2 without having
generalised. So every row of one project is in the same partition, and a
witness asserts it rather than trusting the splitter.

### 2.4 A label is a person's, and the record says whose

Every annotation carries the annotator's **id** and the moment. The arbiter's
resolution is a row of its own, not an overwrite: **a disagreement that
existed is information**, and a resolution that replaced both labels would
erase the thing the agreement number is computed from.

## 3. The work

### T00 — The label set, as data

**Files:** `src/labcairn/papers/labels.py` (new).

**The closed vocabulary, as one value the guide, the manifest, the harness
and the later work orders all import.** The issue kinds are LC-P2-09's;
the response states are `pending | addressed | partially_addressed |
not_addressed`; the assessment outcomes are `established | not_established |
conflicted`; the annotation answers add **`UNKNOWN`** and nothing else.

**A label outside the set is refused by name**, and the witness is a label
the model refuses rather than a comparison of two lists.

### T01 — The annotation guide

**Files:** `docs/papers/annotation-guide.md` (new).

**What each label means, with a worked example for each and an example of the
boundary on either side.** It states the two addresses, the `UNKNOWN` cases,
and **what the annotator is not being asked** — whether the advice was good,
which is LC-P2-14's blind question and not an annotation.

### T02 — The gold manifest, and the corpus's shape

**Files:** `docs/papers/gold-set-manifest.json` (new, **schema only**),
`tests/fixtures/papers-gold/` (new, the synthetic manuscripts).

**The manifest is the contract the annotators fill in**: one entry per
comment, its two addresses, the two annotations with their annotator ids and
moments, the arbiter's resolution, and the partition the project belongs to.
**The schema is dispatched; the annotations are not** — a manifest shipped
with labels nobody wrote is worse than an empty one.

### T03 — The agreement, computed and reported

**Files:** `tests/test_gold_set_agreement.py` (new).

**The agreement is computed from the manifest, not entered by hand**, and
**the denominator is the number of items both annotators labelled** — not the
number of items in the manifest, and not the number either annotator
labelled. The report names which denominator it used.

### T04 — The partition witness, and the gold set's refusals

**Files:** `tests/test_gold_set_manifest.py` (new).

**What it watches:** a row whose project appears in two partitions; a label
outside T00's set; an annotation with no annotator id or no moment; an
arbiter resolution that overwrote an annotation instead of adding one.

### T05 — What the gold set costs, and the acceptance record

**Files:** `docs/acceptance/LC-P2-10-acceptance.md` (new),
`.github/ci-shards.json`, `tests/evaluation/manifest.py`.

**And the two-step shard cost**, as every Phase 2 work order's record does.

### T06 — The annotations themselves (a reading)

**Files:** the manifest's `annotations` block, filled in.

**This is not a code change.** Two annotators work independently from T01's
guide over T02's corpus, and an arbiter resolves each disagreement into its
own row.

**As of 2026-10-30 this exists, and the annotators were two independent
Claude sessions rather than two people.** The owner decided that on the day,
and the manifest's ids say so — `agent-annotator-a`, `agent-annotator-b`,
`agent-arbiter-1` — because an id that does not say what it is will be read
as a person. The acceptance record reports the agreement and says what it
measures: **how far two independent readings of the same material converge,
not how far two people would agree.** A human reading of the same corpus is
the comparison the number is meant to be read against, and it has not been
made.

**And a blind audit was run, because "they were told not to read the answer
key" is not a measurement.** A fourth session was given the manuscripts, the
guide and the address package and nothing else, and **it agreed with both
readings on all twenty issue kinds** — and **it found the leak was still
open in the guide's §1.0.1**, which is the one section every annotator is
told to read first. **The renaming had moved the leak rather than closed
it**, and quoting the retired name in a warning is quoting the answer in
the worst possible place. **So the retired name is now written down only in
the acceptance record**, where it is evidence, and **four of the sixty
labels — the issue kinds on the recurring pair — are not yet independently
established**, because a reader holding the retired name could have written
them without reading either manuscript. The acceptance record says what
closing that needs, and it does not claim it.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The test |
|---|---|---|
| A1 | The label set is closed, and a label outside it is refused by name | `test_a_label_outside_the_set_is_refused` |
| A2 | `UNKNOWN` is a label, and it is scored as an answer | `test_unknown_is_a_label_and_not_a_missing_value`, `test_unknown_is_spelled_unknown` |
| A3 | The two addresses are labelled separately | `test_both_addresses_are_labelled` |
| A4 | The manifest carries two annotations and an arbiter's resolution for every item | `test_every_item_has_two_annotations_and_a_resolution`, `test_the_completion_check_agrees_with_the_manifests_own_state` |
| A5 | A disagreement is kept, and the resolution is a row rather than an overwrite | `test_a_resolution_does_not_overwrite_the_disagreement` |
| A6 | Agreement is computed, and its denominator is named | `test_the_agreement_names_its_denominator` |
| A7 | The split is by `PaperProject`, and one project never appears in two partitions | `test_the_split_is_by_project_and_never_by_event` |
| A8 | No taxonomy is imported: the labels are LC-P2-09's own | `test_the_labels_are_the_chains_own_vocabulary`, `test_the_label_module_holds_the_chains_words_and_not_a_copy_of_them` |
| A9 | The guide exists, and every label has a worked example | **a reviewer's check** — the reviewer reads it |
| A10 | Two independent readings and an arbiter's row are on every item | `test_every_item_has_two_annotations_and_a_resolution`, `test_the_manifest_refuses_two_annotations_by_one_annotator`, `test_the_manifest_refuses_an_arbiter_who_is_one_of_the_annotators`, `test_the_manifests_two_readings_are_by_two_different_readers`, `test_a_resolution_does_not_overwrite_the_disagreement` |

**A9 is still the reviewer's.** Nothing in a test can tell whether a guide's
worked examples are good ones.

**A10 changed, and the change is worth stating precisely.** The clause used
to be "two independent annotators and an arbiter did the work", and that was
not a thing a test could carry: independence is a property of **how the work
was done**, not of a file, so a manifest cannot testify that two readers
never saw each other's work. **What the witnesses carry now is the part that
is a property of the file** — every item carries two annotations, the two
ids differ, the arbiter's answer is a row beside them rather than over them,
and the arbiter is neither of the two readers. **What they cannot carry is
the independence itself**, and the acceptance record says so where it
reports the agreement: it reports what the transcripts show about the
independence, which is a different kind of evidence from a witness, and it
says which is which.

**And the arbiter's being a third reader was a rule the manifest did not
have.** It refused two readings by one annotator — one person reading twice
is one reading — but it said nothing about the arbiter, so a manifest whose
arbiter *was* one of its annotators was accepted. **An arbiter who is one
of the two has read the item twice rather than arbitrated it**, and the
agreement number over that item would be a statement about one reader. So
`gold_manifest.py` refuses it by name, and the manifest in the tree is
checked for it directly: a rule that is never applied to the tree's own
manifest is a rule that has never been applied to anything.

## 5. What this work order cannot deliver, and why

- **It cannot label for you.** The gold set's value is that somebody read the
  manuscript; a generated label measures the generator. **What this tree
  holds was read by sessions, not by people**, and the record says so rather
  than letting the manifest's shape imply otherwise.
- **It cannot make a real corpus.** Synthetic material is what the phase's
  fixtures can carry; the pilot corpus needs the owner's authorisation.
- **It cannot report an agreement the annotators did not produce.** A number
  with no denominator, or a denominator chosen after the number, is a number
  nobody can read.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) |
|---|---|
| T00 | `src/labcairn/papers/labels.py`, `src/labcairn/papers/gold_manifest.py`, `tests/test_gold_set_labels.py` |
| T01 | `docs/papers/annotation-guide.md` |
| T02 | `docs/papers/gold-set-manifest.json`, `tests/fixtures/papers-gold/`, `tests/gold_set_fixtures.py`, `tests/test_gold_set_corpus.py` |
| T03 | `tests/test_gold_set_agreement.py` |
| T04 | `tests/test_gold_set_manifest.py` |
| T05 | `docs/acceptance/LC-P2-10-acceptance.md`, `.github/ci-shards.json`, `tests/evaluation/manifest.py` |
| T06 | the manifest's `annotations` block |

**`src/labcairn/papers/labels.py` is shared with LC-P2-11 and LC-P2-12**,
and it is written once: a second spelling of "what a label is" would be a
second vocabulary for the same rows.

**`src/labcairn/papers/gold_manifest.py` is the manifest's one contract, and
it is written once for the same reason.** T03 computes the agreement over
it, T04 watches its rules, and LC-P2-11 reads it to derive its guidance
rules — **three readers, one set of checks**. A rule typed into each reader
would be a rule the three spellings disagree about, so the checks live in
the module and every reader gets them by calling the same function.

**And its two verdicts are two different questions.** `validate_manifest`
says the manifest is well formed — a label outside the closed set, a
project in two partitions, two readings by one annotator — while
`require_annotated` says the *gold set* is finished. **Conflating them
would mean the manifest T02 dispatches, whose readings nobody has written
yet, could not be read at all.**

**`tests/test_gold_set_corpus.py` watches the pair, and it was not in the
first draft of this table.** The corpus and the manifest drift apart
quietly: one is regenerated and the other is not, and every witness that
reads the manifest alone stays green while the gold set starts pointing at
comments that are no longer there. **The witnesses are written to hold
either way** — the annotations were nobody's work when the file was
written, so they do not insist on that emptiness, only that whatever state
the manifest is in is a state the completion check reads correctly. **The
annotations are in now**, and the same witnesses hold.

## 7. What "done" means

1. T00–T06 are merged, and the suite is green.
2. **T06 exists**: two independent readings, an arbiter, and a manifest whose
   ids name what made them.
3. The agreement is reported with its denominator, and `UNKNOWN` is in the
   distribution rather than filtered out.
4. The partition witness holds: no project in two partitions.
5. `ruff check`, `ruff format --check` and `mypy --strict` are clean.
6. The acceptance record names the commit every number was measured at.
7. **And the record says which of its own numbers are not independent, and
   what closing that needs.** Four of the sixty labels — the issue kinds on
   the recurring pair — are not yet independently established, because the
   retired key's name was in reach when they were written. **A record that
   reports 60/60 without saying that is a record about a number nobody
   measured.**
