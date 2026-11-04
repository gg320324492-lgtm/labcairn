# LC-P2-11 — the fourth ring, opened: five judgements and the shape that blocked the rest

**The question the ring answers.** Whether a rule's standard shows up in a
**later version of the same manuscript** — not whether the advice was accepted,
which is a fact about the process, but whether the later draft bears it out. The
owner chose on 2026-11-03 to have the judgements made case by case by the
coordinating session, with the grade decided per case, and to start from the
comment-derived rules.

**Measured on** `docs/debt-closures` at `d693521`, against the pilot store. The
store was `0db2e3a3e4976aa8…` before the five rows were written and
`6c956096f07c1b3eac54c1a0c79b4121f846c2a68ec78e82fb5621ad9e17fe33` after; **the
only table that changed is `followup_assessments`**, and it went from 0 rows to
5. No manuscript text is quoted in this record: a passage is described by what
it reports, never reproduced.

## 1. The funnel, measured rather than assumed

Thirty-two comment keys are bound to the sixteen comment-derived rules. A case
can be judged by this ring only if it passes three tests, and each test was
applied by looking the case up:

| Test | Cases failing |
|---|---|
| **a readable anchor** — the comment row is `resolved`, names a paragraph, and the anchored text is not empty | **14 of 32** |
| **a later draft** — the commented version has a child in the chain | 9 |
| **not the advisor's own hand** — the matched paragraph of the child carries no tracked insertion | several, counted per case below |

**Result: five of the sixteen comment-derived rules are judgeable.** The eleven
others are not judgeable *by this ring's question*, and they are listed in §4
rather than quietly dropped. Beyond them sit the eight revision-derived rules,
none of which this method can read at all — also §4.

**Re-measured on 2026-11-04, after the SOW (2) data correction** (the store at
schema `0023`; the three deletion-collapse rows re-anchored to their real text,
the thirteen zero-width rows recast as `position`): the anchor test now fails
**12 of 32**, not 14 — the two keys carried by the re-anchored rows read as
anchored — and **six of the sixteen comment-derived rules are judgeable**, not
five. The new sixth is `rule-125072f804bf0f39`: its only anchored case sits on
paragraph 171, whose text the old reader had collapsed to nothing, and the
correction gave it back (ten characters, `fb-71edce76…`). The other re-anchored
key belongs to a rule that was already judgeable through a different case, so
the rule count moves by one, not by two. The numbers above stay as measured at
`d693521` over the `0019` store — a claim about one store state does not carry
to another — and the re-measurement is witnessed the same way: both states were
run through the identical three tests, the before-state reproducing this
record's 14 and 5 exactly. **The sixth rule's assessment was recorded on
2026-11-04, on the owner's approval**, through the same door and under the same
discipline as the five below — `assess-ring4-125072f804bf0f39`, basis
`revised_manuscript`, assessor `model`, graded `observed` because the matched
paragraph of the child carries the caption **byte for byte**, and the omission
is seen rather than concluded: the comment asks for before-and-after figures
made from the data, and at that address the child draft's addition is numeric
prose in the body text, not a figure. **All six rows read `not_established`.**

## 2. The five assessments

*(Five rows as written on 2026-11-03; the sixth, recorded 2026-11-04 after the
data correction made its rule judgeable, is described in §1 above — six rows
now, all `not_established`.)*

All five were written **through `record_assessment`**, none by SQL, and each
carries `basis="revised_manuscript"`, `assessor_kind="model"` — the judgement is
the coordinating session's, and the vocabulary has a name for that — and an
outcome. **Every one of the five came out `not_established`.** Three are graded
`observed` and two `inferred`, and the grade is the whole distance between them:

*`observed`* — the next draft carries the commented paragraph **byte for byte**.
The passage the comment targets reports a mean particle size and no peak; the
following draft reports the same mean in the same words. What the advisor asked
for is not there, and that is seen, not concluded. So too for the proportional
statistic that gained no sample size, and for the methods paragraph that gained
neither a derivation from the material's properties nor a return to the stated
research question.

*`inferred`* — the passage moved. Where the nearest paragraph in the next draft
matches at 0.177, or the whole address was rewritten at 0.125, the reading rests
on a match rather than on an identity, and the record says so instead of raising
the grade to make the finding look firmer.

**The similarity numbers locate the paragraph; they are not the verdict.** The
verdict is what the two texts say when read beside each other.

## 3. Two things about addressing, both found because a check refused

**A locator key does not name a document.** The first draft of the recording
script carried the two locator keys — the commented paragraph and its counterpart
in the next draft — and on one rule **both sides resolved to the same string**,
because the paragraph is identical in both files and the key describes a shape,
not a document. An assessment whose evidence says `w:p[11]` twice has not said
which draft was read. Every ref is therefore `<version_id>:<locator_key>`, and
each one is resolved back through `paper_versions` → `source_texts` before the
door is called.

**One address, one text — and the store keeps four rows to say it.** The same
resolution then returned **4 rows for one address**: `source_texts` holds
42,276 rows over 14,765 distinct (bytes, key) addresses, **12,634 of them written
by more than one `extraction_version`** — the reader has been re-run over the same
bytes four times and each version kept its rows. The count is not the property;
**what a reader needs is that the address yields one text**, and that is what is
now checked: for every ref, `count(distinct text_sha256) = 1`. The five recorded
refs all pass it.

**The door was proved on the real store, not only in tests.** `record_assessment`
was called with `issue_key='iss-no-such-issue-anywhere'` against
`proj-pilot-1`: it refused with `chain_assessment_issue_not_found`, and the probe
row count came back **0**.

## 4. What this piece does not carry

**The eleven comment-derived rules that could not be judged, by the test that
failed them.** Four have no readable anchor at all and no later draft either; the
rest are each blocked by exactly one test. `rule-268fe33dc66ca924` (3 cases),
`rule-de233a78c5be6d4d` (2), `rule-f3bf302cb3df39c8` (1) and
`rule-fb6500a39ca983b7` (1) sit on the **newest** draft of their project — there
is no later version to read, and the ring has nothing to say about them.
`rule-125072f804bf0f39`, `rule-3550b3e245fdee58`, `rule-4da1e823cb3afa4f`,
`rule-af3ea5561e6c8217`, `rule-bafe38a22815e7e4`, `rule-e288246e5eae415c` and
`rule-789806193d1568c3` are blocked by the empty anchor or by the advisor's own
hand in the child paragraph.

**And the container is the real finding, not the count.** Two structural facts
came out of the attempt:

1. **A "later version" in this material is often the advisor's marked-up copy,
   not the author's next draft.** Pilot-1's `v03 → v03-copy` step is a month later
   by the documents' own clock, and the copy's `accepted` view carries up to 38
   tracked insertions by the advisor at a single paragraph. Treating that as the
   advice borne out would **credit the advice with its own restatement**. So the
   ring's premise needs a distinction the chain does not currently make: an edge
   to the author's next draft versus an edge to a copy someone else marked up.
   **How this was measured:** for each case, the tracked events at the matched
   paragraph of the child version were counted, and a child carrying events by the
   advisor was excluded from judgement — that exclusion is the third test in §1.
   The design answer — whether such an edge belongs in the chain at all, or must
   be labelled — is the owner's.**

2. **None of the eight revision-derived rules can be read this way at all.** All
   thirty of their cases have `prose_edit = 0`: the mentor wrote his instruction
   **as a new paragraph** — the rejected view of that paragraph is empty, so there
   is no earlier wording to compare against, and the next draft has no paragraph
   that corresponds to it. The distillation chose the longest inserted text, so
   it chose the advisor's notes, and they are good rules for it — but the fourth
   ring's question, "did the same place in the later draft take this up?", has no
   place to be asked. Answering it for those rules means reading the whole later
   draft for the thing requested, which is a different claim from the one this
   ring records.

**Two debts for the ledger, both measured here.** *14 of the 32* comment keys the
rules are bound to carry no anchored words, and the split is the point: **7 say
`resolved` and name a paragraph, yet hold no text** — `anchor_start = anchor_end =
0` **and a 64-character digest which is the SHA-256 of the empty string**,
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, a value that
appears in **24 of the table's 80 rows** and was checked here against the digest
computed on the spot. The other 7 are honestly `unknown` — 3 of them still name
the paragraph, 4 do not. **A row that says it is anchored while recording an
integrity value over nothing is worse than a row that says it could not anchor**:
the second names its state, the first would pass any check that only asks whether
a digest is present. The door that writes it does not refuse it — the same shape
as the hole [LC-P2-11-assessment-door](LC-P2-11-assessment-door.md) closed for
`issue_key`: one path validated, the other trusted.

**What the five rows do not do.** The retrieval serves **9** rules and reports
**15** unserved, re-measured after the write through the product's own doors —
**unchanged**. An assessment is a judgement about a case; it is not a judgement
that a comment was answered, and it does not make a rule serveable.
