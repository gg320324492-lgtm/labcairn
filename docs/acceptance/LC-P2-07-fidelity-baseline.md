# LC-P2-07 — DOCX revision fidelity: the baseline measurement, and the reader

**Date:** 2026-10-29 · **Re-measured:** 2026-11-01 · **Base commit:**
`66dde87` · **Measured by:** the executor, on the development machine

**What this record is.** The fidelity measurement for LC-P2-07, run against
the synthetic corpus in `tests/docx_corpus.py`. It answers one
question: **when a reader opens a Word file with tracked changes, how much
of the revision history does it recover?**

**And the reader it is a baseline for.** `src/labcairn/material/ooxml.py` is
LC-P2-07's deliverable, and §5 records what it scores against these
numbers. The measurement was written **before** the reader, on purpose: a
scoring function written after the parser exists tends to score what the
parser does.

**What it is not.** It is not a benchmark of real Word documents. The corpus
is synthetic, the arms are particular versions, and every number below is a
number *about this corpus, on this machine*.

**What changed on 2026-11-01.** The corpus gained one fixture —
`29-comment-spanning-two-paragraphs`, a comment whose range spans two
paragraphs, which is the case the owner's real material turned out to hold
and this corpus did not have. **Every number below was re-measured on that
date and none was carried forward.** On the same date the reader itself
was fixed for the double-read real material exposed — one tracked change
reported as two events across a drawing's text box — and §5.6 records the
defect, the fix, the mutations and what the fix moves downstream. The same
re-measurement added `30-revision-in-drawing-textbox` to the corpus (§5.6
says why: a corpus-wide witness can only catch what the corpus holds), and
every count in §2 and §4 is the 30-fixture corpus, re-measured, not the
29-fixture one.

**The re-measurement also corrected four things the first record got
wrong**, and they are worth naming because each is a way a record drifts
from the measurement:

1. **The invocation in §1 did not run.** `python -m
   tests.evaluation_docx_fidelity` stops with `ModuleNotFoundError`.
2. **The revision breakdown counted 12 insertions.** There are 16; the
   breakdown did not add up to the total it claimed.
3. **The correction table in §4.5 said a fixture was extracted that is in
   fact lost.** §4.5 says which and why.
4. **The record implied the measurement had scored the reader.** It had
   not — the measurement's `ooxml-native` arm is still the *not written
   yet* placeholder, and §5 says where the reader's numbers come from
   instead.

---

## 1. How to reproduce it

```bash
# the corpus and its gold are written by the fixture module
python tests/evaluation_docx_fidelity.py --corpus-dir=<dir>

# with the comparison arms installed (they are NOT project dependencies)
uv run --no-project --with docx2python --with python-docx \
  python tests/evaluation_docx_fidelity.py --corpus-dir=<dir> --json=report.json
```

**The module is run as a file, not as `python -m tests.…`.** It imports
its corpus as top-level modules (`docx_corpus`, `docx_fixtures`), which
are importable only when `tests/` itself is on the path — and
`python -m tests.evaluation_docx_fidelity` puts the *repository root*
there instead, so it stops with `ModuleNotFoundError: No module named
'docx_corpus'`. Running the file puts `tests/` on the path, which is what
the module expects. (The first version of this record named the `-m` form,
which does not run.)

**The arms are installed with `uv run --with`, not added to
`pyproject.toml`.** A measurement tool that adds its subjects to the
product's dependency list would change the product it measures. The
isolation is the point, and it is the same rule the design applies to the
reference repositories.

**The corpus test** — `tests/test_docx_fixture_corpus.py` — checks the
corpus itself, before any of this runs. 100 cases, all green.

## 2. The corpus

| | |
|---|---|
| Fixtures | **30** |
| Revisions | 35 (8 deletions, 21 insertions, 6 moves) |
| Comments | 15 (5 of them deliberately un-anchorable) |
| Paragraphs | 1–12 per fixture |

Each fixture isolates one behaviour and states its purpose and its
expectations. The negative list is the design's §7 list: insertion,
deletion, comment spanning a revision, several authors, an orphan comment
marker, a move pair, nesting, a revision with no author, a revision with no
date, a comment with no anchor, a comment whose range spans two paragraphs,
non-ASCII text, markup characters, and an empty revision.

**The last case is the one the real material found.** The corpus's
twenty-ninth fixture holds a comment whose `w:commentRangeStart` is in one
paragraph and whose `w:commentRangeEnd` is in the next — which is what Word
writes for a comment covering several paragraphs, and what **four
comments across the owner's three bodies of real material** turned out to
contain. The corpus did not have the case, so the witness that checked the
anchored text against the offsets had never seen it. **A witness that has
never seen the case is not a witness to it**, and the corpus's job is to be
the case.

**The corpus found two of its own bugs before it found anything else**, and
both are worth recording because they are what a synthetic corpus is for:

1. The first version emitted the revision elements at the **front** of the
   paragraph, so pandoc's `--track-changes=accept` and `--track-changes=reject`
   gave the same text. A revision's position inside the paragraph is
   load-bearing, and the corpus's test caught the fixture being wrong
   rather than the reader.
2. The first version carried **hand-written character offsets**, which
   pointed at a different part of the sentence than the revision's own text.
   The offsets are now **derived from the text** — a deletion names the
   baseline words it removes, an insertion names the words it follows — and
   the writer refuses to build a fixture whose anchor does not occur in its
   baseline.

The second is the more important finding. **A hand-written expectation
drifts away from the thing it describes.** The derived one cannot.

## 3. The measurement

| Arm | What it is |
|---|---|
| `ooxml-native` | LabCairn's own reader — **the arm is still a placeholder**; §5 says where the reader's numbers are measured instead |
| `pandoc` | text extraction, `--track-changes=accept\|reject\|all` |
| `python-docx` | the library this project already depends on for *writing* DOCX |
| `docx2python` | an extraction library that does handle comments |

**Six columns, and each answers a different question.**

| Column | The question |
|---|---|
| revision recall | did the arm report the changes as **events**? |
| comment recall | did the arm report the comments? |
| deletion recovery | did the arm recover the **deleted text**? |
| accept view correct | is the text-as-if-accepted exactly right? |
| reject view correct | is the text-as-if-rejected exactly right? |
| attributes | can the arm say **who** made a change? |

**Precision and recall are separate, and false negatives are counted
separately from false positives.** A metric that counted only the comments
an arm got right would let an arm that returns *nothing* score perfectly.
An arm that could not read a file is counted as missing everything, not
excluded from the average — excluding it would let an arm that fails on
every fixture report an average over the fixtures it happened to read.

## 4. The result

```
corpus: 30 fixtures, 35 revisions, 15 comments, 8 deletions

arm            rev found rev miss  rev rec cmt found cmt miss  cmt rec   del recov  accept ok  reject ok  attr
--------------------------------------------------------------------------------------------------------------
ooxml-native           0       35    0.000         0       15    0.000     0/8        0/30       0/30       no
pandoc                 0       35    0.000         0       15    0.000     0/8       27/30      30/30       no
python-docx            0       35    0.000         0       15    0.000     0/8       14/30      20/30       no
docx2python            0       35    0.000         7        8    0.467     0/8       24/30      10/30       no
```

**Measured on 2026-11-01, on the development machine, against the corpus at
that date.** The `ooxml-native` row is still a row of zeros because the
measurement's own OOXML-native arm is still the *not written yet*
placeholder — see §5, where the reader's numbers are measured instead.

### 4.1 No arm reports a revision as an event

**All three comparison arms report zero revisions out of thirty-five.** Not one
of them says "this text was deleted on this date by this person".

That is the measurement's central finding, and it is not a defect in the
arms — it is what a *text* is. A reader that produces text has, by
construction, no place to put "who did this", and the phase needs that
place to exist. **This is why the OOXML-native arm has to be a new reader
rather than a configuration of an existing one.**

### 4.2 No arm recovers a deletion

**Zero of eight deletions were recovered by any arm.** The deleted text
lives in `w:delText`, not `w:t`, and every text-producing reader reads
`w:t`.

The upstream study predicted this for Docling from its source
(`msword_backend.py:2053`); the measurement confirms it for all three arms
on this corpus. For a project whose thesis is *"the deletion is the
signal"*, this is the number that matters most, and it is zero.

### 4.3 `pandoc` — the best text arm, and it still loses an edit

pandoc's rejected view is **exactly right on all 30 fixtures**. Its
accepted view is right on **27**.

**The three it gets wrong are `06-insertion-without-author`,
`08-insertion-without-author-or-date`, and — since this re-measurement —
`30-revision-in-drawing-textbox`.** The first two are a specific defect:
pandoc silently drops a tracked insertion that carries no `w:author`. The
two fixtures' XML differ in that attribute and in nothing else, and the
inserted text is present in one accepted view and absent from the other.
The third is the drawing's text box: pandoc renders the box's paragraphs
into the accepted view **twice**, once per `mc:AlternateContent` branch,
where the reader reports them once from the paragraphs they live in.

This was found by measurement, not by reading pandoc's source, and it is
the design's §7 case "a document with no author" — where the correct
answer is **UNKNOWN, not gone**. A reader that discards the change has
turned "we do not know who did this" into "nobody did this", and the
difference is invisible in the output.

### 4.4 `python-docx` — the project's own dependency, and the weakest text arm

`python-docx` is already a dependency of this project (LC-P1-11's report
export). It is also the **worst** of the three text arms: its accepted view
is right on 14 of 30 and its rejected view on 20.

**The accepted view is worse than the rejected one, and that asymmetry is
the finding.** `python-docx`'s `Run.text` reads `w:t` only, so a deleted
run reads as empty — the deletion leaves no trace in the text it produces.
The rejected view is closer because the baseline text is still there.

### 4.5 `docx2python` — it handles comments, and it loses half of them

**Comment recall 0.467: seven of fifteen comments recovered, eight lost.**

The six fixtures where comments were lost are exactly the ones the design
names:

| Fixture | Lost | Why |
|---|---|---|
| `13-orphan-comment-end-only` | 1 of 1 | the range ends without starting — **the library raises** |
| `14-comment-without-anchor` | 1 of 1 | no range markers at all |
| `21-multiple-comments-and-revisions` | **2 of 2** | one unpaired marker took the whole set |
| `22-long-document` | 1 of 1 | the comment is un-anchored |
| `23-everything-at-once` | **2 of 2** | one unpaired marker took the whole set |
| `28-comment-on-empty-paragraph` | 1 of 1 | the range covers empty text |

**The `21` and `23` rows are the important ones: a single unpaired marker
takes every comment in the document with it.** The mechanism is in
`docx_output.py:418` — the library compares the number of comment ranges
with the number of comment elements and, when they differ, warns and
returns an empty list.

**The correction to the upstream study.** The study of docx2python, read
from source, recorded this as "the whole comment set disappears on any
mismatch". The measurement is more precise, and the precise version
matters for the parser's requirements:

| Case | Counts | Result |
|---|---|---|
| `12-orphan-comment-start-only` | 1 range, 1 element — the counts **match** | the comment **is** extracted, with an empty anchor |
| `13-orphan-comment-end-only` | 1 range, 1 element — the counts **match** | the comment is **lost, and the library raises** |
| `14-comment-without-anchor` | 0 ranges, 1 element — the counts **differ** | the comment is **lost entirely** |

**The correction found on 2026-11-01.** The first version of this record
said that `13-orphan-comment-end-only` "**is** extracted, with an empty
anchor". **It is not.** The counts do match — one range, one element — so
the count check does not fire, and the library then looks the range up
**by the comment's id** and does not find it: the range is keyed by an end
marker with no start behind it, so the lookup raises `KeyError: '206'`
while the document is being read (`depth_collector.py:214`). The
measurement counts an arm that raises as an arm that could not read the
file, and the fixture is in the lost column above. **The first record's
correction table and its "six fixtures" table contradicted each other on
this row, and the measurement settles it: the comment is lost.**

So the trigger is **not only** the count mismatch. A range that starts and
never ends survives, because the counts balance and the id is found; a
range that ends and never started does not, because the id lookup fails
before an anchor is ever computed; and a comment with no marker at all
takes the whole set with it, because the counts differ. **Either way the
anchor is lost**: the caller either receives a comment with an empty
reference and no indication that the anchor was there, or receives nothing
at all, because the library raised.

**The new fixture's measurement of docx2python.**
`29-comment-spanning-two-paragraphs` is **recovered** by docx2python — one
range, one element, the counts match — and the anchor it reports is **the
two paragraphs joined together**:

> The method estimates the parameter from a single observation.The estimate
> is reported with its confidence interval, and the interval is computed
> over ten random seeds.

That string is in no paragraph of the document. **It is the same defect
this record's §5.2 is about, reached by a different road**: a reader that
reports a text the file does not contain, where the comment's own range
marks two paragraphs and no paragraph holds the text between them.

**The second measurement of docx2python: its anchor is the whole
paragraph, not the comment's range.** On `11-two-comments-one-paragraph`,
two comments on different parts of one paragraph both report the same
anchor text — the paragraph's. A mentor's "this phrase" becomes "this
paragraph", which is a materially weaker claim.

### 4.6 What the measurement says about the design

| The design asked | The measurement says |
|---|---|
| *"OOXML 原始 ZIP/XML 只读解析优先"* — read the XML directly | **Supported.** No text arm reports a revision as an event; none recovers a deletion. |
| *"普通文本转换只能作为对照视图"* — plain-text conversion is a comparison view only | **Supported and sharpened.** pandoc's rejected view is exact on 30/30, which makes it a good *comparison* and a poor *source*. |
| *"Docling/docx2python/Pandoc 与原始 XML 的保真率做对照报告"* | **Done here**, for three of the four; Docling is not installed and is not needed to make the finding, which is structural rather than specific to it. |
| *"对缺失元数据输出 UNKNOWN，不伪造作者和时间"* | **Supported.** pandoc discards such an edit entirely, which is the failure this rule exists to prevent. |

## 5. The reader, measured against this baseline

**`src/labcairn/material/ooxml.py` is written against ECMA-376 / ISO-IEC
29500, and it is held to the numbers above.** The reader's column below is
measured by **the reader's own tests** (`tests/test_ooxml_revisions.py`),
each of which asserts one of these numbers against the corpus.

**The measurement tool's `ooxml-native` arm is still the *not written yet*
placeholder**, and it is still a row of zeros in §4. **That arm is not
wired to the reader.** The measurement module is not this record's
deliverable, and a row of zeros the tool did not produce is more honest
than a row it did.

| Property | The baseline | The reader |
|---|---|---|
| revision recall | 0 of 35 for every text arm | **35 of 35** |
| deletion recovery | 0 of 8 for every text arm | **8 of 8** — the text, not an empty run |
| comment recall | 0.467 (docx2python), 0 for the rest | **15 of 15**, including the five un-anchorable |
| the anchor is the comment's **range** | paragraph-granular (docx2python) | **the range** |
| a missing author or date | — | `UNKNOWN`, never a guess |
| the original bytes | — | unchanged, and the module has **no write path at all** |

### 5.1 How the reader reaches the deleted text

**The deleted text lives in `w:delText`, and every text-producing reader
reads `w:t`.** That is the whole of the difference, and it is why the
reader reads the XML itself.

**The view is part of the address.** A Word document reads two ways, and
ADR-0014 D4 names them: *accepted* and *rejected*. The same character range
means different characters in each, so `DocxLocator` carries a `view`
field and the rendered key carries it too — two addresses for one element
in the two views are different addresses, and they resolve to different
text, which is correct because they *are* different text.

**The deleted text has an address because of that field.** It is not in
the accepted view at all, so no range there could name it. A `w:del`
element's text in the **rejected** view is exactly the deleted text, and
that is the locator the deletion event carries.

### 5.2 The five un-anchorable comments, and what each one says

The reader does not lump them. A range that starts and never ends, a range
that ends and never started, a comment with no range at all, and a range
whose two markers sit in different paragraphs are **four different
defects**, and each is reported with its own reason:

| Case | The reader's answer |
|---|---|
| the range starts and never ends | the comment, with an **unknown anchor** and the reason *"the comment's range starts but never ends"* |
| the range ends and never started | the comment, with an **unknown anchor** and the reason *"the comment's range ends but never starts"* |
| no range markers at all | the comment, with an **unknown anchor** and the reason *"the comment carries no range markers"* |
| the range spans two paragraphs | the comment, with an **unknown anchor** and the reason *"the comment's range spans two paragraphs"* |

**The comment's body, author and date are reported in all four cases**,
because they are in the file. Dropping them is the failure the upstream
study found in a library, and it is what §5.4's second mutation does.

### 5.2.1 The fourth case, and why it is the one that bites

**A range that spans two paragraphs looks resolvable and is not.** Word
writes a comment covering several paragraphs with its `w:commentRangeStart`
in the first and its `w:commentRangeEnd` in the last, and **each marker
carries an offset within its own paragraph**. The two offsets are
therefore offsets into two different texts, and the pair names no range
that exists.

**The reader used to pair them.** It reported the start marker's paragraph
with the end marker's offset — an address that resolves to text nobody
wrote. On the corpus that is **characters 0–106 of a 61-character
paragraph**; on the owner's `v03-chinese-draft.docx` it is comment 192,
stored as **paragraph 64, characters 0–134**, in a paragraph whose baseline
is **10 characters** long, with the end offset borrowed from paragraph 67.

**An address that names no text is not a text.** So the anchor is now
reported as **unknown**, with its own reason, and the offsets are not
reported at all. The paragraph the range *starts* in is kept — that much
is a fact about the file — and the comment's body, author and date are
untouched.

**The schema cannot catch this one, and the reader therefore has to.** The
`feedback_events` CHECK constraint requires an unknown anchor to carry a
reason and no offsets, and this row satisfies it — but a *resolved* anchor
whose end offset was borrowed from another paragraph satisfies the
constraint too, because the schema has no vocabulary for "this range names
text outside its paragraph". **Only the reader can refuse that**, which is
why the reader's own test asserts the offsets slice the paragraph they
name rather than trusting the row to catch it later.

**This is the contract the feedback chain is built against.** A chain
whose links are addresses cannot carry a link that names no text. **The
owner's pilot chain measured it**: of forty-six recorded comments,
eighteen had an empty anchored text under a status of `resolved`, and
three of the eighteen were this case. The other fifteen were legitimate
zero-length ranges, where the offsets and the text agree.

**The witness for it was right; the corpus was missing the case.** The
invariant — the anchored text agrees with the offsets — was already
watched (`tests/test_feedback_events.py`, A2), but the synthetic corpus
held no cross-paragraph comment, so the witness had never seen the case
the real material has. **A witness that has never seen the case is not a
witness to it.** The corpus now holds it, and two new tests watch it:
`test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor`
and `test_a_resolved_anchor_never_names_a_range_outside_its_own_paragraph`.

### 5.3 What the reader refuses

| Case | The refusal |
|---|---|
| bytes that are not a Word document | `docx_unreadable` — inventoried and hashed, and *no* history extracted, because a history we could not read is not an empty history |
| an archive with no `word/document.xml` | `docx_part_absent` |
| a part that declares a **DTD** | `docx_part_refused`, naming the part — entity expansion is a denial-of-service vector and this reader does not expand entities |
| a comment the body references but the archive does not hold | `docx_comment_reference_unknown` — the reference is real and points at nothing, and the comment is not invented |
| a revision nested inside another revision | `docx_nested_revision` — the inner one is reported separately with its own path and text |

### 5.4 The mutations, and what each one broke

**A witness that has never been broken is not known to be a witness.** Eight
mutations were applied to the reader and to the corpus that carries it, and
each is named with the test that caught it. Mutations 5–8 were applied on
2026-11-01, for the cross-paragraph case.

| # | The mutation | What went red |
|---|---|---|
| 1 | the deleted text is dropped instead of read from `w:delText` | `test_every_deletion_text_is_recovered`, `test_every_revision_carries_its_kind_text_author_and_date`, `test_the_two_views_are_the_texts_adr_0014_names`, `test_a_revision_nested_inside_another_is_reported_separately` |
| 2 | a comment whose anchor does not resolve is dropped — **the upstream library's bug** | `test_every_comment_is_reported_including_the_unanchorable_ones`, `test_a_comment_with_no_resolvable_anchor_is_still_a_comment`, `test_each_unresolvable_anchor_names_its_own_reason` |
| 3 | a missing author is filled in with a placeholder | `test_a_missing_author_or_date_is_unknown_and_never_guessed`, `test_every_revision_carries_its_kind_text_author_and_date` |
| 4 | the locator forgets the view | `test_a_revision_locator_resolves_to_the_revisions_own_text`, `test_a_deletion_is_addressed_in_the_rejected_view` |
| 5 | a range that spans two paragraphs is reported as **resolved**, with the end marker's offset borrowed from the other paragraph | `test_a_comment_with_no_resolvable_anchor_is_still_a_comment`, `test_each_unresolvable_anchor_names_its_own_reason`, `test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor`, `test_a_resolved_anchor_never_names_a_range_outside_its_own_paragraph` |
| 6 | the cross-paragraph case reports a **non-empty** anchored text — a plausible-looking fragment of the first paragraph | `test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor` — **and nothing else**, which is why that test exists |
| 7 | the fixture builder writes the range's end marker in the paragraph the range **starts** in, so the range no longer spans two | `test_a_comment_with_no_resolvable_anchor_is_still_a_comment`, `test_each_unresolvable_anchor_names_its_own_reason`, `test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor` |
| 8 | the gold's derivation says the cross-paragraph anchor **resolves** | `test_a_comment_with_no_resolvable_anchor_is_still_a_comment` (the count of un-anchorable fixtures falls from 5 to 4) |

**Mutation 7 is the one that shows the corpus really carries the case.**
A fixture that claims to hold a cross-paragraph range but does not would
be a fixture that tests nothing — and the corpus's own test would stay
green, because it checks the gold against the XML and the XML would be
consistent with the gold. **Only the reader's test can tell that the
fixture has stopped being the case it names**, and it does.

**One mutation survived, and the reason matters.** It was "the reader
writes to the file it read", and it **survived** — the whole file was green
— because `read_document` takes **bytes** and therefore *cannot* change the
file they came from. The property held by construction, not by the
reader's care, and the file-bytes test was watching something that could
not fail.

**That is a weak witness, and it has been replaced.** The strong half is
now `test_the_reader_module_writes_nothing`, which reads the reader's
**source** and refuses any write call in it. A mutation that adds a
`write_bytes` to the module is caught by that test — verified, and the
verification is recorded here because the first attempt at it did not
apply (the mutation's text did not match the formatted source), which is
how a mutation can be reported as surviving when it was never applied.

**The lesson is the project's own**: *"a measurement that is transcribed is
a measurement that can be wrong."* The same holds for a mutation that was
never applied. Both were caught by asking what the number actually
measured.

### 5.5 The cases the corpus cannot reach

They are tested against documents built in the test file, and the corpus's
`KNOWN_GAPS` says why they are not there: **a part that declares a DTD**,
and **a corrupt archive**. The other shapes this section once tested only
by hand — a revision nested inside another revision, and a revision inside
a drawing's text box (§5.6) — are in the corpus now: `19-nested-revision`
carries the nesting in its XML, and `30-revision-in-drawing-textbox` was
added with §5.6, because the corpus-wide witnesses can only catch what the
corpus holds. The hand-built drawing test stays: it asserts what the
fixture's gold does not — which paragraph reports a text-box revision, and
that none of them is nested.

### 5.6 The double-read: one tracked change, two events

**Found by real material, on 2026-11-01.** One of the corpus's
advisor-marked drafts — a pilot review copy, kept out of the tree with the
rest of the real material — held **239 revision elements** counted straight
from `word/document.xml`, and the reader reported **243** events. Four
tracked changes were read a second time, and each of the four collided
with its own address: two events, one `(part, element_path)`, one derived
row id.

**The shape, and why the reader doubled it.** A paragraph's run carried a
figure — Word's routine `mc:AlternateContent`, whose `Choice` carries the
modern drawing and whose `Fallback` carries the VML copy, **each branch
wrapping a text box of paragraphs of its own**. `read_document` scans
every paragraph `iter` finds, and `iter` finds the text box's paragraphs
as readily as the body's; the outer paragraph's walk then crossed the
drawing containers on its way down and reported the box's `w:ins`
elements a second time. Two scanners, one element, two events.

**The fix names the reporter.** A revision is reported by **the paragraph
that contains it** — the nearest one. The outer walk still advances the
offset through the box (the outer paragraph's text counts the box's text
either way, and `_scan_paragraph`'s two coordinate systems must agree),
but from the first nested `w:p` downward it reports no revision and no
comment marker: the box's paragraphs are scanned as paragraphs, and they
report their own. Nested revisions inside one paragraph's run content are
untouched — `test_a_revision_nested_inside_another_is_reported_separately`
stayed green throughout.

**What the double-read never did, and why the fix is still owed.** The
chain's writer (`record_revision_events`) skips an event whose id and
text hash match an existing row, and the four duplicates collided only
with **themselves** — same element, same path, same text — so the pilot's
chain holds no row the double-read wrote: **measured on the pilot's
`revision_events`, the affected version holds 239 rows against 239
distinct addresses, zero surplus**. But that is a coincidence wearing a
contract: had two *different* revisions ever shared one address, the
second would have been dropped silently as a replay of the first. After
the fix the reader's addresses are unique by construction —
`_element_path` indexes same-tag siblings, and one element is reported
once — so `_revision_event_id`'s claim (*the element's path is unique
inside a part*) is true because the reader makes it true, and its
docstring says so.

**The verification, on the real file and on every review copy the corpus
holds.** After the fix the affected draft reads **239 events against 239
distinct addresses and 239 elements**; every other review copy that holds
revisions (384, 349, 311, 225, 219, 219, 210, 203, 114, 52, 27 and 8
elements respectively) read event-for-event identical to before. The
corpus's witness is
`test_a_revision_inside_a_drawing_textbox_is_reported_once`, built on the
real shape (Choice and Fallback, a text box each, two revisions in each),
and `test_the_reader_reports_each_revision_element_exactly_once` holds the
reader to the count over the whole synthetic corpus.

**The mutations, numbered on from §5.4's eight:**

| # | The mutation | What went red |
|---|---|---|
| 9 | the walk reports inside nested paragraphs again — the defect restored | `test_a_revision_inside_a_drawing_textbox_is_reported_once`, and — once `30-revision-in-drawing-textbox` joined the corpus — the corpus-wide witnesses too (`test_every_revision_in_the_corpus_is_reported`, `test_every_revision_carries_its_kind_text_author_and_date`, `test_the_reader_reports_each_revision_element_exactly_once`, `test_the_derived_revision_event_id_names_one_change_per_address`) |
| 10 | `_element_path` stops indexing same-tag siblings (`index = 1` always) | all three new witnesses: the drawing test, the per-element count, and the id witness |
| 11 | `_revision_event_id` drops the element path from its digest | `test_the_derived_revision_event_id_names_one_change_per_address` |
| 12 | `_revision_event_id` mixes the wall clock into its digest | **survived** — on Windows two calls land inside one clock tick, and the id came out the same; re-applied as *every call counts itself* (`itertools.count`), and the id's determinism witness went red |

Mutation 9 was first measured **before** fixture 30 existed, and only the
hand-built test went red — the corpus held no shape for its count to
catch, which is exactly why the fixture was added. The review that found
the gap ran mutation 9 alone against the pre-fixture corpus and the
corpus-wide count survived; re-measured against the corpus as it now
stands, it does not. A corpus-wide witness is as good as the corpus's
data, and the fixture exists to keep that true.

Mutation 12's first form is recorded because it is how a mutation can be
real and still survive: the property ("the same inputs, the same id") and
the mutation ("the clock is in the digest") were both true, and the tick
boundaries decided the outcome. A survivor is re-measured with a mutation
that cannot be so timing-lucky before it is believed.

**The extraction version moved.** `derive_extraction_version` hashes the
reader's own source, so the fix moves the version the way it is designed
to: **`d375f3a81242e9cbbd6075155d67f365` before, `38e0d9591c8e2a9a13c913b5f2b5f0f3`
after** (measured on this machine; the after value is the hash of
`src/labcairn/material/ooxml.py` at the fix's commit `f4a7e94`, and a
later change to that file moves it again).

**What that means for the pilot's chain.** The chain's rows are snapshots
written by the reader that was running — *the chain is written by the
reader's version* — and the pilot's `revision_events` carry the old
parser version. Re-running the operator's recording step against the
fixed reader is **idempotent, not a rewrite**: the same file yields the
same addresses, the same derived ids and the same texts, and every row
matches the row already there — the four duplicates are simply gone
before they reach the writer. What changes is only what a **new**
ingestion writes: its rows will carry the new parser version. The pilot's
existing rows are not invalidated by the fix (the fix changes how many
*events* a read reports, not what any one address holds), but they are
not refreshed by it either.

**And one defect this work found and did not fix.** Counting revision
elements straight from the package also exposed a file where the reader
reports **fewer** events than the part holds revision elements: a table
row's insertion marker (`w:trPr/w:ins`, an empty element **outside** any
paragraph) is invisible to a scan that walks paragraphs. That is the
opposite failure from §5.6's — a revision the reader never reports, not
one it reports twice — and it is **not fixed here**; it belongs to its
own work order, and the count that found it is recorded so it cannot be
forgotten.

## 6. The numbers this does **not** establish

- **Nothing about real Word documents.** The corpus is synthetic. A real
  Word file fragments a revised sentence across several runs, renumbers
  revision ids on save, and puts comments in headers and footnotes. The
  corpus's `KNOWN_GAPS` lists ten such cases; the pilot corpus is where
  they are obtained.
- **Nothing about Docling.** It was not installed. Its source reading
  (`docs/research/upstream-study/docling.md`) predicts the deletion loss,
  and the prediction is confirmed for the other three arms — but Docling's
  own number is not measured here, and this record does not claim it.
- **Nothing about the OOXML-native arm's behaviour on real documents.** §5
  records what it does on the synthetic corpus — revision recall 1.0,
  deletion recovery 1.0, comment recall 1.0 — and that is a number about
  **this corpus**, whose revisions are one element each, whose comments
  live in `word/comments.xml`, and whose paragraphs are plain runs. The
  ten cases in the corpus's `KNOWN_GAPS` are the ones a real Word file
  brings and this one does not: run fragmentation inside a revision, Word
  renumbering revision ids on save, comments in headers and footnotes, a
  document whose revisions have been accepted, and the rest.
- **Nothing about how a reader performs on the pilot corpus.** That is a
  second measurement, and it is the one that decides whether the reader is
  good enough.
- **Nothing about the corpus's range granularity.** The corpus's writer
  emits a comment's range markers around **whole paragraphs** — the start
  marker before the paragraph's first run and the end marker after its
  last — rather than at the offsets the fixture's `anchor_text` names. So
  on this corpus the reader's resolved anchor for a well-formed comment
  *is* the paragraph, and **the corpus cannot tell "the reader reports the
  comment's range" from "the reader reports the paragraph"**. The reader
  reports the range the markers name, and the markers in this corpus are
  paragraph-granular; the difference is exercised by the real material,
  where a comment's markers sit inside the paragraph. **The §5 row "the
  anchor is the comment's range" is therefore a statement about the
  reader's rule, not a number this corpus measures.**
- **Nothing about the reader's behaviour on a document the corpus cannot
  write.** §5's numbers are numbers about the corpus's files. The owner's
  real material found a case the corpus had not (§5.2.1), and it is
  recorded here as the reason the corpus grew — **the next real document
  may find another one.**

## 6. What this record asked of LC-P2-07, and what answered it

| The requirement | Answered by | Measured |
|---|---|---|
| **The OOXML-native reader must recover every revision and every deletion on this corpus**, with the author and date reported as `UNKNOWN` where the file omits them. Zero of the comparison arms manage this. | `src/labcairn/material/ooxml.py` | 35 of 35 revisions, 8 of 8 deletions |
| **The reader must report every comment, including the five whose anchor is unresolvable**, with an unknown anchor and a reason naming the unmatched marker. `docx2python` loses eight of fifteen; the requirement is fifteen of fifteen with five of them marked unknown. | the same | 15 of 15, five of them with a reason |
| **The reader's anchor must be the comment's range, not the paragraph's.** Measured against `docx2python`'s paragraph-granular anchor. | the same | the range — with §6's stated limit on what this corpus can tell |
| **The reader must not modify the original bytes.** | the same, and a source-level watch on the module | unchanged, and the module has no write path |
| **A parser that returns nothing must not score well.** The false-negative floor in §3 is what keeps that true, and it must survive into
   the acceptance test.

## 7. The commits and the environment

| | |
|---|---|
| Base commit | `66dde87` (first measurement); re-measured on 2026-11-01 on the development machine, against the corpus with `29-comment-spanning-two-paragraphs` added |
| Corpus | `tests/docx_corpus.py`, `tests/docx_fixtures.py` |
| Corpus test | `tests/test_docx_fixture_corpus.py` (103 cases; 100 measured here, 3 added with fixture `30-revision-in-drawing-textbox`) |
| Measurement | `tests/evaluation_docx_fidelity.py` |
| **The reader** | `src/labcairn/material/ooxml.py` |
| **The reader's test** | `tests/test_ooxml_revisions.py` (27 cases; 24 measured here, 3 added with §5.6) |
| **The migration** | `migrations/versions/0009_docx_locator.py` — **unchanged**: the anchor vocabulary is `'resolved' \| 'unknown'` and this change adds a *reason*, not a value |
| pandoc | 3.10 (installed on the machine; GPL-2.0, used as a comparison only) |
| python-docx | the project's own declared dependency, 1.2.0 |
| docx2python | 66b1ae3e24ffa7040ed5244490ce2872ac2e86bb (version 3.7.2) |
| Python | 3.12.13 (the project's virtualenv) |

**How the 2026-11-01 re-measurement was run.** The `docx2python` arm was
run against the local checkout at
`66b1ae3e24ffa7040ed5244490ce2872ac2e86bb` — the SHA this record already
names — with the `paragraphs` dependency taken from the project's uv
cache, because the machine had no network and `uv run --with` could not
fetch it. **The same numbers came out of the cached wheel** (docx2python
3.7.2), so the arm's numbers do not depend on which of the two was used.
pandoc 3.10 and python-docx 1.2.0 were used as before.

**The repository is clean at the base commit apart from the files this
work adds.** The measurement writes its corpus outside the repository — the
project's own rule, that a run's working directory must not be inside the
checkout.
