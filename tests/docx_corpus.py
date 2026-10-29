"""The synthetic DOCX corpus: one fixture per case the parser must handle.

Twenty-eight fixtures, each isolating one behaviour of a revision-aware
reader. The corpus is organised by what the fixture is *for*, and each
fixture's ``purpose`` says so in one line, because a corpus whose cases are
named only by filename teaches nothing.

**The cases come from three places**, and the third is the one that matters:

1. The design's §7 negative list — insertion, deletion, comment spanning
   runs, several authors, an orphan comment marker, moves, table changes,
   a document with no date, a document whose revisions have been accepted,
   a corrupt ZIP.
2. What the upstream study found — that a deleted run's text lives in
   `w:delText` and not `w:t`, so a reader that looks only at `w:t` loses
   every deletion; that a comment whose range markers do not pair can take
   the whole comment set with it.
3. What a real Word corpus will contain and this one cannot — recorded in
   `KNOWN_GAPS` at the bottom, so the gap is a list and not a surprise.

**How a fixture is anchored.** A revision names the text it affects by
*what that text means*, not by a character offset:

- a **deletion** names the baseline words it removes (``anchor_text``);
- an **insertion** names the baseline words it follows (``after_text``),
  because an insertion adds at a point rather than replacing anything.

The character range is derived from those, in
`tests/docx_fixtures.py`. The first version of this corpus carried
hand-written offsets, and they were wrong: they pointed at a different part
of the sentence than the revision's own text, so the fixture's accepted and
rejected views were both nonsense — and the corpus's own test caught it.

**On the gold.** Every fixture states its expected parse result. The gold
is written from the same words that write the XML, but it is a separate
artefact: a parser is checked against the gold, never against the fixture
writer's internals.
"""

from __future__ import annotations

from docx_fixtures import Comment, Fixture, Revision

#: The corpus.
#:
#: Ordered from the simplest case to the most awkward, so that a reader
#: working down the list is never blocked by a case that depends on one
#: below it.
FIXTURES: list[Fixture] = [
    # -- 1. the baseline ---------------------------------------------------- #
    Fixture(
        name="01-clean-no-revisions",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
        ),
        purpose="A document with no revisions at all: the baseline a parser must not embellish.",
        expectations=(
            "Zero revision events.",
            "Zero comments.",
            "The accepted and rejected texts are identical, and equal to the body text.",
        ),
    ),
    # -- 2. the ordinary cases ---------------------------------------------- #
    Fixture(
        name="02-single-insertion",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
        ),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="101",
                paragraph=0,
                after_text="The method estimates the parameter from",
                note="A plain insertion with an author and a date.",
            ),
        ),
        purpose="One insertion with full metadata: the case every other case is measured against.",
        expectations=(
            "One revision event of kind 'ins'.",
            "Its text is 'carefully' and its author and date are present.",
            "The accepted text contains the inserted text; the rejected text does not.",
        ),
    ),
    Fixture(
        name="03-single-deletion",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
        ),
        revisions=(
            Revision(
                kind="del",
                text="a single observation",
                author="Prof. Lin",
                date="2026-03-02T09:20:00Z",
                element_id="102",
                paragraph=0,
                anchor_text="a single observation",
                note=(
                    "The deleted text lives in w:delText. A reader that reads only "
                    "w:t sees an empty run and the text is simply gone."
                ),
            ),
        ),
        purpose="One deletion: the case the whole phase exists to get right.",
        expectations=(
            "One revision event of kind 'del'.",
            "Its text is 'a single observation' — NOT empty.",
            "The rejected text contains the deleted text; the accepted text does not.",
        ),
    ),
    Fixture(
        name="04-insert-and-delete",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
        ),
        revisions=(
            Revision(
                kind="del",
                text="a single",
                author="Prof. Lin",
                date="2026-03-02T09:20:00Z",
                element_id="103",
                paragraph=0,
                anchor_text="a single",
            ),
            Revision(
                kind="ins",
                text="repeated",
                author="Prof. Lin",
                date="2026-03-02T09:21:00Z",
                element_id="104",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
        ),
        purpose="A deletion and an insertion in one paragraph: the replacement case.",
        expectations=(
            "Two revision events, one 'del' and one 'ins'.",
            "They are distinct events with distinct ids, not one merged 'replace'.",
            "The accepted text says 'repeated' and the rejected text says 'a single'.",
        ),
    ),
    Fixture(
        name="05-two-authors",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
        ),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="105",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
            Revision(
                kind="ins",
                text="rigorously",
                author="Dr. Chen",
                date="2026-03-03T14:00:00Z",
                element_id="106",
                paragraph=0,
                after_text="a single observation.",
            ),
        ),
        purpose="Two authors in one paragraph: authorship is per-event, not per-document.",
        expectations=(
            "Two revision events with two different authors and two different dates.",
            "Neither author's name leaks into the other's event.",
        ),
    ),
    # -- 3. the metadata that is missing ------------------------------------ #
    Fixture(
        name="06-insertion-without-author",
        paragraphs=("The method estimates the parameter from a single observation.",),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author=None,
                date="2026-03-02T09:15:00Z",
                element_id="107",
                paragraph=0,
                after_text="The method estimates the parameter from",
                note="No w:author attribute at all — which is what Word writes.",
            ),
        ),
        purpose="An insertion with no author: the answer is UNKNOWN, never a guess.",
        expectations=(
            "One revision event.",
            "Its author is UNKNOWN and author_present is false.",
            "The author is NOT inferred from the document, the file name or the context.",
        ),
    ),
    Fixture(
        name="07-insertion-without-date",
        paragraphs=("The method estimates the parameter from a single observation.",),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date=None,
                element_id="108",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
        ),
        purpose="An insertion with no date: UNKNOWN, and never the file's mtime.",
        expectations=(
            "One revision event.",
            "Its date is UNKNOWN and date_present is false.",
            "The file's modification time is NOT used as a substitute.",
        ),
    ),
    Fixture(
        name="08-insertion-without-author-or-date",
        paragraphs=("The method estimates the parameter from a single observation.",),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author=None,
                date=None,
                element_id="109",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
        ),
        purpose="Neither author nor date: both are UNKNOWN, and neither is filled in.",
        expectations=(
            "One revision event.",
            "Both author and date are UNKNOWN.",
            "The event still exists — missing metadata does not delete the change.",
        ),
    ),
    # -- 4. the comments ----------------------------------------------------- #
    Fixture(
        name="09-comment-with-anchor",
        paragraphs=("The method estimates the parameter from a single observation.",),
        comments=(
            Comment(
                comment_id="201",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Which observation? State the assumption.",
                paragraph=0,
                anchor_text="a single observation",
            ),
        ),
        purpose="A comment with a paired range: the normal case, with the anchor resolvable.",
        expectations=(
            "One comment with its body, author and date.",
            "Its anchor resolves, and anchor_status is 'resolved'.",
            "The anchored text is the text between the range markers.",
        ),
    ),
    Fixture(
        name="10-comment-spanning-a-revision",
        paragraphs=("The method estimates the parameter from a single observation.",),
        revisions=(
            Revision(
                kind="del",
                text="a single",
                author="Prof. Lin",
                date="2026-03-02T09:20:00Z",
                element_id="110",
                paragraph=0,
                anchor_text="a single",
            ),
        ),
        comments=(
            Comment(
                comment_id="202",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Why is one observation enough?",
                paragraph=0,
                anchor_text="a single",
            ),
        ),
        purpose="A comment whose range contains a revision: the two features must not interfere.",
        expectations=(
            "One comment and one revision event.",
            "The comment's anchor resolves and covers the deleted text.",
            "The revision's text is reported even though it sits inside the comment range.",
        ),
    ),
    Fixture(
        name="11-two-comments-one-paragraph",
        paragraphs=("The method estimates the parameter from a single observation.",),
        comments=(
            Comment(
                comment_id="203",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Define the parameter.",
                paragraph=0,
                anchor_text="the parameter",
            ),
            Comment(
                comment_id="204",
                author="Dr. Chen",
                date="2026-03-02T10:00:00Z",
                text="State the assumption.",
                paragraph=0,
                anchor_text="a single observation.",
            ),
        ),
        purpose="Two comments on one paragraph: one bad anchor must not take the other with it.",
        expectations=(
            "Two comments, both returned.",
            "Each has its own anchor range and its own author.",
        ),
    ),
    Fixture(
        name="12-orphan-comment-start-only",
        paragraphs=("The method estimates the parameter from a single observation.",),
        comments=(
            Comment(
                comment_id="205",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="The range never closes.",
                paragraph=0,
                anchor_text="a single observation",
                anchor="start_only",
            ),
        ),
        purpose=(
            "A comment whose range starts and never ends: the case that makes a "
            "library drop the entire comment set."
        ),
        expectations=(
            "The comment is STILL returned, with its body, author and date.",
            "Its anchor_status is UNKNOWN, and the reason names the unmatched marker.",
            "The parser does not report 'no comments' for a document that has one.",
        ),
    ),
    Fixture(
        name="13-orphan-comment-end-only",
        paragraphs=("The method estimates the parameter from a single observation.",),
        comments=(
            Comment(
                comment_id="206",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="The range never starts.",
                paragraph=0,
                anchor_text="a single observation",
                anchor="end_only",
            ),
        ),
        purpose="A comment whose range ends without starting: the mirror of the previous case.",
        expectations=(
            "The comment is STILL returned.",
            "Its anchor_status is UNKNOWN.",
        ),
    ),
    Fixture(
        name="14-comment-without-anchor",
        paragraphs=("The method estimates the parameter from a single observation.",),
        comments=(
            Comment(
                comment_id="207",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="General note about the whole paragraph.",
                paragraph=0,
                anchor_text="",
                after_text="",
                anchor="none",
            ),
        ),
        purpose=(
            "A comment with no range markers at all: a comment that survives in "
            "comments.xml while its anchors were deleted."
        ),
        expectations=(
            "The comment is STILL returned, with its body.",
            "Its anchor_status is UNKNOWN.",
            "It is NOT hung on the paragraph text as though it were anchored there.",
        ),
    ),
    Fixture(
        name="15-comment-without-author",
        paragraphs=("The method estimates the parameter from a single observation.",),
        comments=(
            Comment(
                comment_id="208",
                author="",
                date="2026-03-02T09:30:00Z",
                text="An anonymous remark.",
                paragraph=0,
                anchor_text="a single observation",
            ),
        ),
        purpose="A comment with an empty author: distinct from a comment with no author attribute.",
        expectations=(
            "The comment is returned with an empty author.",
            "An empty author is not the same as a missing one, and neither is filled in.",
        ),
    ),
    # -- 5. the moves --------------------------------------------------------- #
    Fixture(
        name="16-move-from",
        paragraphs=(
            "Introduction. Prior work on estimation is extensive.",
            "The method estimates the parameter from a single observation.",
        ),
        revisions=(
            Revision(
                kind="moveFrom",
                text="Prior work on estimation is extensive.",
                author="Prof. Lin",
                date="2026-03-04T11:00:00Z",
                element_id="111",
                paragraph=0,
                anchor_text="Prior work on estimation is extensive.",
            ),
        ),
        purpose="A move source: the text moved away, and the reason must survive the move.",
        expectations=(
            "One revision event of kind 'moveFrom'.",
            "Its text is present in the recorded event.",
            "The accepted text drops it; the rejected text keeps it.",
        ),
    ),
    Fixture(
        name="17-move-to",
        paragraphs=(
            "Introduction. Prior work on estimation is extensive.",
            "The method estimates the parameter from a single observation.",
        ),
        revisions=(
            Revision(
                kind="moveTo",
                text="Prior work on estimation is extensive.",
                author="Prof. Lin",
                date="2026-03-04T11:00:00Z",
                element_id="112",
                paragraph=1,
                after_text="The method estimates the parameter from a single observation.",
            ),
        ),
        purpose="A move destination: a move is two events, and the pair must be recognisable.",
        expectations=(
            "One revision event of kind 'moveTo'.",
            "Its text matches the moveFrom's text in the paired fixture.",
        ),
    ),
    Fixture(
        name="18-move-pair",
        paragraphs=(
            "Introduction. Prior work on estimation is extensive.",
            "The method estimates the parameter from a single observation.",
        ),
        revisions=(
            Revision(
                kind="moveFrom",
                text="Prior work on estimation is extensive.",
                author="Prof. Lin",
                date="2026-03-04T11:00:00Z",
                element_id="113",
                paragraph=0,
                anchor_text="Prior work on estimation is extensive.",
            ),
            Revision(
                kind="moveTo",
                text="Prior work on estimation is extensive.",
                author="Prof. Lin",
                date="2026-03-04T11:00:00Z",
                element_id="114",
                paragraph=1,
                after_text="The method estimates the parameter from a single observation.",
            ),
        ),
        purpose="A complete move pair: the case a diff-based method gets wrong.",
        expectations=(
            "Two revision events, 'moveFrom' and 'moveTo'.",
            "The accepted text has the sentence once, in its new place.",
            "The rejected text has it once, in its old place.",
        ),
    ),
    # -- 6. the structural cases ---------------------------------------------- #
    Fixture(
        name="19-nested-revision",
        paragraphs=("The method estimates the parameter from a single observation.",),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="115",
                paragraph=0,
                after_text="The method estimates the parameter from",
                note="An insertion, with a deletion nested inside it.",
            ),
        ),
        purpose=(
            "Nesting is representable; a parser that flattens it loses the "
            "difference between 'inserted then deleted' and 'inserted'."
        ),
        expectations=(
            "The nested structure is preserved, not flattened.",
            "The parser reports the nesting, or reports it as unsupported.",
            "It never silently flattens it.",
        ),
    ),
    Fixture(
        name="20-revision-in-every-paragraph",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
            "The results are summarised in Table 1.",
        ),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="116",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
            Revision(
                kind="del",
                text="described in",
                author="Dr. Chen",
                date="2026-03-02T09:40:00Z",
                element_id="117",
                paragraph=1,
                anchor_text="described in",
            ),
            Revision(
                kind="ins",
                text="precisely",
                author="Prof. Lin",
                date="2026-03-02T09:45:00Z",
                element_id="118",
                paragraph=2,
                after_text="The results are summarised in",
            ),
        ),
        purpose="A revision in every paragraph: the parser must not lose one of them.",
        expectations=(
            "Three revision events, one per paragraph.",
            "Each names its own paragraph.",
        ),
    ),
    Fixture(
        name="21-multiple-comments-and-revisions",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
        ),
        revisions=(
            Revision(
                kind="del",
                text="a single",
                author="Prof. Lin",
                date="2026-03-02T09:20:00Z",
                element_id="119",
                paragraph=0,
                anchor_text="a single",
            ),
            Revision(
                kind="ins",
                text="repeated",
                author="Dr. Chen",
                date="2026-03-03T08:00:00Z",
                element_id="120",
                paragraph=1,
                after_text="We evaluate on the benchmark",
            ),
        ),
        comments=(
            Comment(
                comment_id="209",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Justify the single observation.",
                paragraph=0,
                anchor_text="a single",
            ),
            Comment(
                comment_id="210",
                author="Dr. Chen",
                date="2026-03-03T08:05:00Z",
                text="Which benchmark version?",
                paragraph=1,
                anchor_text="the benchmark",
            ),
        ),
        purpose="The mixed case: comments and revisions across paragraphs, by different people.",
        expectations=(
            "Two revision events and two comments.",
            "Every one of the four is returned; none is swallowed by the others.",
        ),
    ),
    Fixture(
        name="22-long-document",
        paragraphs=tuple(
            f"Paragraph {i}. The method estimates the parameter from observation {i}."
            for i in range(1, 13)
        ),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="121",
                paragraph=5,
                after_text="Paragraph 6. The method estimates the parameter from",
            ),
            Revision(
                kind="del",
                text="observation 7",
                author="Dr. Chen",
                date="2026-03-03T08:00:00Z",
                element_id="122",
                paragraph=6,
                anchor_text="observation 7",
            ),
        ),
        comments=(
            Comment(
                comment_id="211",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Tighten this.",
                paragraph=5,
                anchor_text="Paragraph 6.",
            ),
        ),
        purpose="A twelve-paragraph document: the offsets must not drift across paragraphs.",
        expectations=(
            "Twelve paragraphs, one revision in each of two of them, one comment.",
            "Every event names the paragraph it is actually in.",
        ),
    ),
    # -- 7. the whole-lot cases ------------------------------------------------ #
    Fixture(
        name="23-everything-at-once",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "We evaluate on the benchmark described in Section 3.",
            "The results are summarised in Table 1.",
            "Prior work on estimation is extensive.",
        ),
        revisions=(
            Revision(
                kind="del",
                text="a single",
                author="Prof. Lin",
                date="2026-03-02T09:20:00Z",
                element_id="123",
                paragraph=0,
                anchor_text="a single",
            ),
            Revision(
                kind="ins",
                text="repeated",
                author="Prof. Lin",
                date="2026-03-02T09:21:00Z",
                element_id="124",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
            Revision(
                kind="moveFrom",
                text="Prior work on estimation is extensive.",
                author="Dr. Chen",
                date="2026-03-04T11:00:00Z",
                element_id="125",
                paragraph=3,
                anchor_text="Prior work on estimation is extensive.",
            ),
            Revision(
                kind="moveTo",
                text="Prior work on estimation is extensive.",
                author="Dr. Chen",
                date="2026-03-04T11:00:00Z",
                element_id="126",
                paragraph=0,
                after_text="The method estimates the parameter from a single observation.",
            ),
        ),
        comments=(
            Comment(
                comment_id="212",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Support this claim.",
                paragraph=0,
                anchor_text="the parameter",
            ),
            Comment(
                comment_id="213",
                author="Dr. Chen",
                date="2026-03-03T08:05:00Z",
                text="Cite the benchmark version.",
                paragraph=1,
                anchor_text="the benchmark",
                anchor="start_only",
            ),
        ),
        purpose=(
            "Everything at once: insertions, a deletion, a move pair, two "
            "comments and one malformed anchor."
        ),
        expectations=(
            "Four revision events and two comments, all of them returned.",
            "The malformed comment's anchor is UNKNOWN; the well-formed one resolves.",
            "No event is lost to the others.",
        ),
    ),
    Fixture(
        name="24-duplicate-text-two-paragraphs",
        paragraphs=(
            "The method estimates the parameter from a single observation.",
            "The method estimates the parameter from a single observation.",
        ),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="127",
                paragraph=1,
                after_text="The method estimates the parameter from",
            ),
        ),
        purpose=(
            "Two identical paragraphs: an anchor that says only 'the text' cannot "
            "say which one, so the paragraph must be part of the anchor."
        ),
        expectations=(
            "One revision event, in paragraph 1 — not paragraph 0.",
            "The event's paragraph distinguishes the two identical texts.",
        ),
    ),
    Fixture(
        name="25-revision-with-empty-text",
        paragraphs=("The method estimates the parameter from a single observation.",),
        revisions=(
            Revision(
                kind="ins",
                text="",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="128",
                paragraph=0,
                after_text="The method estimates the parameter from",
            ),
        ),
        purpose="A revision with no text at all: an event that exists but changes nothing.",
        expectations=(
            "The event is reported, with empty text.",
            "It is not silently dropped for being empty.",
        ),
    ),
    Fixture(
        name="26-unicode-text",
        paragraphs=(
            "我们使用单一观测来估计参数。",
            "The confidence interval is ±0.05 (95%).",
        ),
        revisions=(
            Revision(
                kind="del",
                text="单一",
                author="林教授",
                date="2026-03-02T09:20:00Z",
                element_id="129",
                paragraph=0,
                anchor_text="单一",
            ),
        ),
        purpose=(
            "Non-ASCII text and an author name: character offsets are counted in "
            "characters, not bytes."
        ),
        expectations=(
            "The deleted text is '单一', not mojibake.",
            "The author's name is '林教授'.",
        ),
    ),
    Fixture(
        name="27-markup-characters",
        paragraphs=("The result is significant (p < 0.05) & reproducible.",),
        revisions=(
            Revision(
                kind="ins",
                text="<em>strongly</em> & clearly",
                author="Prof. Lin",
                date="2026-03-02T09:15:00Z",
                element_id="130",
                paragraph=0,
                after_text="The result is significant (p < 0.05)",
            ),
        ),
        purpose="Markup characters in the text: the XML must be escaped, not passed through.",
        expectations=(
            "The inserted text is the literal '<em>strongly</em> & clearly'.",
            "The document parses, and the ampersand is not treated as an entity.",
        ),
    ),
    Fixture(
        name="28-comment-on-empty-paragraph",
        paragraphs=(
            "",
            "The method estimates the parameter from a single observation.",
        ),
        comments=(
            Comment(
                comment_id="214",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                text="Start the section here.",
                paragraph=0,
                anchor_text="",
                after_text="",
            ),
        ),
        purpose="A comment on an empty paragraph: the anchor is empty, and that is not an error.",
        expectations=(
            "The comment is returned.",
            "Its anchor resolves to an empty range on paragraph 0.",
        ),
    ),
]


#: What this corpus cannot reach, so the gap is a list and not a surprise.
#:
#: Every item here needs a real Word file or a Word-generated one, and the
#: pilot corpus is where they are obtained. Each names the behaviour a
#: parser must have, so that obtaining the file is a task rather than a
#: vague request for "some real documents".
KNOWN_GAPS: tuple[str, ...] = (
    "Run fragmentation inside a revision: Word splits a revised sentence "
    "across several w:r runs, so a parser that assumes one run per change "
    "reads a fragment.",
    "w:moveFromRangeStart/End and w:moveToRangeStart/End: the markers that "
    "pair a move, without which a move is two unrelated events.",
    "Revision ids renumbered on save: Word rewrites w:id on every save, so "
    "an id is not stable across two saves of the same document.",
    "w14:paraId and w14:textId collisions: the identifiers Word uses for "
    "paragraph identity, which are not unique in a damaged file.",
    "Comments in headers, footers, footnotes and endnotes: the range and "
    "the comment element live in different parts, so a parser reading only "
    "word/document.xml misses them.",
    "Comments carried in the commentsExtended part (w15): the reply and "
    "done-state fields that a newer Word writes.",
    "A document whose revisions have been accepted: the file no longer "
    "holds the history, and the correct answer is 'no revisions', not "
    "'a deletion happened'.",
    "A corrupt ZIP: the reader must refuse with a reason rather than "
    "raising, and must not write anything.",
    "A .docx whose document.xml declares an encoding the archive does not use.",
    "Real advisor prose: the fixtures carry English sentences about a "
    "parameter, and real comments carry hedging, politeness and typos.",
)
