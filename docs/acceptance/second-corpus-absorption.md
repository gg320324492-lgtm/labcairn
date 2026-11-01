# The second body of material — what it was, how it was read, and what it found

**Status:** the reading is done and arbitrated; the chain holds it; the
distillation's question is written down and **nothing has been sent**. The
second corpus's rules are **not** in the memory yet — the model's answer
awaits the owner's answer on whether it may be sent.

**Where the material is:** `E:\labcairn-local\materials-library\corpus-2-recycling-4404737\`,
in the owner's own library. **Nothing of it is in this repository**: not the
manuscript, not a comment, not a label, not the agreement number. The
repository carries the method and the product's findings; the library
carries the bytes.

---

## 1. What the second body of material is

**It is a different paper from the first.** The first corpus is the
drinking-water disinfection study on micro-nanobubbles. The second
corpus's advisor material is a **composting study** — kitchen-waste digestate
and straw, under forced aeration and turning — and its three advisor-marked
copies are **three revisions of that one manuscript by three different
people**:

| The advisor's copy | Comments | Tracked revisions | What the advisor did |
|---|---|---|---|
| the first | 25 | 349 | wrote beside the text, word by word |
| the second | 0 | 58 | **rewrote silently** — no remark at all |
| the third | 9 | 0 | **criticised the paper as a whole** |

**The copies' own names are not in this record**, because the
project's practice for the first corpus was to keep the advisor's identity
out of the repository along with the manuscript, the labels and the
agreement number. **What each advisor did is a fact about the material and
it is stated; who each of them is is the owner's business.** The
library holds the names, and this record can be checked against it.

**And that is the finding the first corpus could not produce.** One
advisor's hand is at the level of the word, one's is at the level of the
whole paper, and one's is at the level of the sentence with no words
written beside it at all. **A role design that reads the chain must be
able to say which of those it is looking at**, because the three call for
different things: a card about a word is a card about the wording, and a
card about the whole paper is not a card about anything the card's
`target_locator` can name.

**The paper's own title changes across the three copies**, so the copies
are three states of one paper and not three annotations of one state.
**The chain records them as three versions of a second project and asserts
no order between them** — which is right, because the material does not
say which came first, and ADR-0014 refuses to let a file name decide.

## 2. How it was read

**The same procedure as the first corpus**, and the same guard: the two
readers never saw each other's work, and neither saw an answer key.

| | Where |
|---|---|
| the reading's input | `corpus-2-recycling-4404737/advisor-guidance/reading-input-corpus2.json` |
| reader 1's reading | `…/reading-corpus2-1.json` |
| reader 2's reading | `…/reading-corpus2-2.json` |
| the arbiter's resolution of all 34 items | `…/arbiter-corpus2.json` |
| the agreement, and the arbiter's resolutions | `…/blind-readings-corpus2.json` |

**The agreement is 0.8235 over 34 items** — 28 agreed, 6 disagreed. The
first corpus's was 0.9167 over 12 items and over 34.

**And the lower number is a fact about the guide, not about the
readings.** Every one of the six disagreements is in one advisor's file,
and the two readers independently named the same three places where the
guide does not settle the question: a remark asking for an unnecessary
sentence to be cut, a term the reader cannot parse, and a missing link
between two measurements. The arbiter followed one reader on each of the
six, gave no third label, and returned **no `unknown`** — every one of the
six could be tied to a clause of the guide.

**The arbiter also named five things the guide does not settle**, and they
are worth the owner's attention more than the number is: the label set has
no place for *redundancy and length*; §3.11 lists terminology but does not
say whether *is this category even one of the physical properties* is a
terminology question; §3.3's boundary does not decide the order of two
things inside one sentence; §3.7 and §3.4 have no boundary clause between
them; and **§2.4's rule 3 bites on this material** — four comments here
carry no visible problem in their anchor, so a body-side `unknown` is what
the guide asks for, while this reading records one label per comment by
the comment's address.

**The reading was done by sessions, not by people.** The agreement number
measures how far two independent readings of the same material converge,
and it does not measure how far two people would agree — the guide says so
itself, and this record says it again because the number will be read
against the gold set's.

## 3. What the chain now holds

**The second corpus is in the product, as a second project.** The first
project is one paper and its seventeen drafts; the second is a different
paper, so it is a different project with its own grant, and the first
project's rows are untouched.

| | Project | Versions | Comments |
|---|---|---|---|
| the drinking-water paper | `proj-pilot-1` | 17 | 46 |
| **the composting paper** | **`proj-pilot-2`** | **3** | **34** |

**And the chain now tells the three shapes apart**, which it could not do
before this batch:

| The comment's shape | How many |
|---|---|
| placed on a passage | 28 |
| not placed in the body — the reader names why | 5 |
| placed on a point — the range covers no text | 1 |

**That last distinction is the batch's product change, and it is what the
material forced.** A comment the reader could not place in the body and a
comment the reader placed on a stretch of manuscript that holds no text
**both carry an empty anchored text**, and the layer dropped the field that
tells them apart. So a rule's scope built from such a case quoted `""` as
though it were the advisor's words — and **six of the pilot's eight
confirmed rules carried a scope that quoted `""`**.

## 4. The two defects the material found

Both are the same shape as the three commits before them: **an address that
claims more than it holds.**

### 4.1 The reader stored an address that names no text

`src/labcairn/material/ooxml.py`'s `_anchor_for` resolved a comment's
anchor from its `w:commentRangeStart` and `w:commentRangeEnd` markers,
and **each marker carries an offset within its own paragraph**. When the
two markers sit in different paragraphs — which is what Word writes for a
comment covering several paragraphs — the reader paired the start
paragraph with the end marker's offset, and stored a range that cannot
exist: comment 192 of `v03-chinese-draft.docx` is **paragraph 64,
characters 0–134, in a paragraph whose baseline is 10 characters long**.

**Four comments across the owner's three bodies of real material hold this
case.** The synthetic corpus held none of it, so the witness that checked
the anchored text against the offsets — `test_the_anchored_text_agrees_with_the_offsets_in_the_version_named`
— **had never seen it**. The corpus now holds one
(`29-comment-spanning-two-paragraphs`), and two witnesses watch it: the
cross-paragraph comment is reported as an unknown anchor with its reason
and its body intact, and **every resolved anchor over the whole corpus
slices the paragraph it names**.

**A range that spans paragraphs is now a fourth named failure mode**, with
its own reason — *"the comment's range spans two paragraphs"* — beside the
three that were already there. The schema's anchor vocabulary is unchanged:
`resolved` and `unknown` are still the only two values, a reason is not a
value, and no migration was needed.

### 4.2 A rule's scope quoted the empty string as the advisor's words

The chain's row already held an `anchor_status` and an `anchor_reason`,
and the application layer's `ChainComment` carried **neither** — so a
caller could not tell a remark the reader could not place from a remark
about a place the reader found and that is empty. `src/labcairn/guidance/
distil.py` built the scope from the anchored text alone, so an unplaced
case contributed `""` to it.

**The layer now carries the status and the reason, and the scope names
every case it holds**: the text the comment was written against, or the
fact that the reader could not place it, with the reason the chain gives.
**The empty string is never quoted as the advisor's words.**

**The pilot's eight confirmed rules keep their stored scope.** A rule's
scope is part of a versioned record the owner confirmed, and correcting a
confirmed record is a person's act — the confirmation door's, not the
product's. The product's next distillation produces a truthful scope.

### 4.3 And the first chain held the same false address

**The pilot's chain was written before the fix, so it still held the old
rows.** Three of the first project's forty-six comments carried the false
address — and **three of the owner's eight confirmed rules cite those
three comments as their cases**: the rule about the manuscript's
numbering, the rule about the method section, and the rule about the
figures.

**The repair rewrote exactly those three rows** with what the fixed
reader reports, and the repair **checked itself**:

| | |
|---|---|
| rows holding an address that names no text | **3 → 0** |
| rows changed | **exactly those three**, and no other |
| the rules, their states, their confirmations and their eighteen sources | **exactly what they were** |
| the comments' own words, authors, dates and issue keys | **untouched** |

**And the anchor's text hash is the same before and after** — the range
covers no text either way — so `record_feedback` would have **kept** the
old row rather than rewriting it. **A chain that holds an address its own
reader would not produce is a chain that says something false**, so the
rows were rewritten deliberately, with the rules left alone: **the rule's
statement is the owner's, and the anchor is the reader's.**

**And after the repair the first project's comments are told apart the
same way the second's are**: 28 placed on a passage, 15 placed on a point,
and 3 the reader could not place — each with its reason named.

## 5. What was measured, and how

| | |
|---|---|
| the reading | 34 comments, two independent readings, one arbiter, **0.8235** agreement |
| the chain | a second project, 3 versions, 34 comments, 3 shapes told apart |
| the reader's fix | **4 real comments** across three bodies of material; 1 synthetic fixture added |
| the witnesses | 4 caught the reader's mutation; 3 caught the scope's |
| the record's own errors | **4 corrected** — an invocation that never ran, a revision breakdown that did not add up, a fixture said to be extracted that is lost, and a claim that the measurement had scored the reader when it had not |

**Every mutation was applied and watched, and every file was restored
byte-for-byte.** One mutation of mine did **not** apply — it changed a
condition that was already false for the case it aimed at, so nothing
observable moved — and the rule that a mutation must be *effective* before
its survival means anything caught it.

## 6. What this batch does not do

- **It does not confirm any rule.** The second corpus's distillation is
  asked for and **not sent**; the model's answer is not in, and nothing
  about it may be read before the owner decides.
- **It does not order the three copies.** The chain holds them as three
  versions with no edge between them, because the material does not say
  which came first.
- **It does not put the manuscript in the repository**, and neither the
  labels nor the agreement number.
- **It does not change the label set.** The owner's decision of
  2026-10-31 holds: the twelve issue kinds stay as the comparable axis,
  and the guide's own unsettled places are **named for the owner** rather
  than patched.
- **It does not say the rules are good.** Whether a rule helps a student
  is LC-P2-14's question. This batch makes them *traceable* — every one
  back to the advisor's own words, through an address that holds.
