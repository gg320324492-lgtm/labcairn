# The fourth pilot: the oil-sludge corpus, its 897 changes, and what they taught

**What this record is.** The third pilot (`LC-P2-11-revision-distillation.md`)
drew two rules from nine tracked changes and, in its second pass, one more from
the acts those changes formed. **The fourth pilot is a corpus of the same
shape at a hundred times the size**: a submission's six drafts, five marked-up
copies a reviewer returned, and one English draft — **897 tracked changes by
one reviewer across five rounds**, with not one Word comment in any file.

**And this corpus carries a second thing the earlier ones did not.** The
reviewer's words are **written into the text** as inserted parentheses — a
question about whether a definition holds, an instruction that a figure be a
bar chart, a demand that a citation stop being a number — so the feedback
arrives in neither of the two shapes the memory already knew. It is a third
shape: **a change that carries its own reason in parentheses**.

**It is also the same reviewer who marked up the second corpus** (the manifest
names him, and the second corpus's record carries him too), which is what
makes the comparison in §4 possible at all: one person's standard across two
papers.

## 1. The ingest

Read from the chain after the run, not from the script's log:

| | |
|---|---|
| Project | `proj-pilot-4`, grant `grant-pilot-read-4` |
| Versions | **12** — six drafts, five marked-up copies, one English draft |
| Version edges | **11** — the order is the dates in the drafts' own file names |
| Revision events | **897** — 614 insertions, 272 deletions, 3 `moveFrom`, 8 `moveTo` |
| Edit actions | **832**, every one carrying actor `advisor` / `tianzhi-wang` |
| Addresses touched | **99** distinct `(version, paragraph)` pairs |
| Comments · links · replies · assessments | **0 · 0 · 0 · 0** |

**Two things were deliberately not recorded, and the reasons are the
material's own.** The three letters under `responses/` are answers, not
manuscripts; recording them as versions of the paper would be a claim the
material does not make. And the seven paired exchanges in the third letter's
`pairs.json` were not written as replies, because **that file's own extraction
block says there was no second reader and no arbiter, and that its addresses
do not resolve** — no document in the corpus carries the line numbering the
reviewer's comments point at. A reply needs a place to hang, and this batch
gives none.

**One roster decision is the operator's, and it is per project.** The same
reviewer's name appears in the first pilot as a student's; here the manifest
calls him the reviewer, so the roster records him as `advisor`. **A name does
not carry a role across corpora.**

## 2. The seven groups, and the six that were confirmed

**The grouping is the operator's reading of the reviewer's acts**, not the
product's; the product minted each case's key, its scope (the paragraph the
changes sit in) and its example (the reviewer's own longest insertion). Each
statement below is a paraphrase, and the case count is what the material
actually gave.

| # | Issue kind | The standard, in one line | Cases | State |
|---|---|---|---|---|
| 1 | `sources` | Citations are authored, not numbered, and a bare "reference" placeholder is not a source | 11 | confirmed |
| 2 | `figures` | Comparisons of one set of conditions are bar charts with error bars, and figures carrying one part of the argument are merged | 3 | confirmed |
| 3 | `figures` | Conclusive photographs and data stay in the text; process photographs and calculations move to the supplement, with a pointer | 2 | confirmed |
| 4 | `introduction_and_storyline` | The introduction runs phenomenon → properties and their literature → the precondition for the work → the gap and the open questions | 3 | confirmed |
| 5 | `data_quality` | An effect nobody analysed is not written up, and is not given an unanalysed cause | 1 | **candidate** |
| 6 | `controls_and_ablation` | Every control is introduced with the question it answers | 2 | confirmed |
| 7 | `method_and_hypothesis` | Key definitions are checked against the group's own papers before they are written | 3 | confirmed |

**Six are confirmed by the owner as a second reader; the seventh is not, and
the reason is the material's.** Rule 5 rests on **one act** — the reviewer
wrote down that an effect worsened, guessed why, and then said keep it out
because nobody had analysed it. It is the sharpest instruction in the corpus
and the thinnest evidence, and **on the owner's decision it stays a
candidate**: one act is a proposal a reader must judge, never a confirmed
standard.

**What the rule memory holds now**: 24 confirmed rules across four projects
(8 + 8 + 2 + 6) and one candidate, plus the two checks bound to the third
pilot's rules.

## 3. What the fourth pilot shows the *capability* does

- **The revision path scales.** Nine changes produced two candidates; 897
  produced seven groups with case counts from 1 to 11. Nothing in the door
  needed changing to read this corpus — the same `distil_candidate_from_revisions`
  minted every case, scope and example.
- **A change can be a comment.** The third shape — a tracked insertion whose
  text is a question or an instruction — is still a revision event, so it is
  already a case; **the product did not need a new shape to hold it.** What it
  needed was an operator who read parentheses as words rather than as
  punctuation.
- **The material still decides the truth.** Five of the seven groups came from
  insertions that carry a sentence; the two that came from deleted or
  reordered text rest on fewer cases, and the record says so.

## 4. The same reviewer, two papers

Measured against the second corpus's eight confirmed rules — same reviewer,
different paper and different subject:

| Where the standard sits | Second corpus | Fourth pilot |
|---|---|---|
| Expression — how the paper argues | 5 rules: novelty, two on language, statistical basis, research question | — |
| Figures | 1 rule: axis and tick legibility, font conventions | 2 rules: chart type, error bars, merging; and main text versus supplement |
| Introduction | 1 rule: logical links between paragraphs, each paragraph's role | 1 rule: the arc the introduction runs and where each paragraph ends |
| Methods and definitions | 1 rule: state the means, the information, the purpose; keep definitions consistent | 1 rule: check the definition against the group's own papers |
| Sources | — | 1 rule: authored citations, not numbered |
| Controls | — | 1 rule: every control says what it answers |
| Data honesty | — | 1 rule (candidate): do not report what was not analysed |

**What this supports.** The standards that appear in both papers are the ones
about **figures, the introduction and method descriptions**, and in each case
the fourth pilot's version is the more specific one — it names the chart type,
the arc, and where to check a definition. The three standards that appear only
here are all about **how evidence is established** (sources, controls, what
may be reported). **So what moved is not "the reviewer got stricter"; it is
that this paper made him ask about evidence rather than about wording.**

**What this does not support.** The two papers have different subjects and
different reviewers' tasks, and **absence is not relaxation**: five of the
second corpus's rules have no counterpart here because this paper did not pose
those questions. **A cross-paper claim needs the same question asked of both
papers**, which this material does not give; the comparison above is a
comparison of what each paper elicited.

## 5. What was not done

- **No rules were drawn from the author's own changes.** The roster knows one
  actor, the reviewer; the drafts carry no tracked changes at all.
- **The seven paired exchanges were not recorded** (§1).
- **Each of the six confirmed rules now names a check — closed 2026-11-03.**
  A question a reader runs against a manuscript and the criterion that answers
  it, confirmed by the owner as a second reader and bound at the rule's
  version; the memory holds **8 checks and 8 bindings** and no candidate
  check. **The negative proof was run on the real rows both times**: binding
  was attempted *before* each confirmation and refused with
  `guidance_check_not_confirmed`, so "a rule may name only a check a person
  has confirmed" is demonstrated rather than quoted. **What the closure does
  not change is the evidence under it**: the six criteria rest on **11, 3, 2,
  3, 2 and 3 acts**, and **none has been tried against a draft the reviewer
  left alone** — the criteria are read out of what he did.
- **A one-act rule is left in the memory as a candidate** (§2), which is the
  state a proposal should be in.

## 6. Where the numbers came from

Every figure in §1 was read back from `E:\labcairn-local\pilot-ws\labcairn.db`
after the run (`paper_versions`, `version_edges`, `revision_events`,
`edit_actions` filtered by `project_id = 'proj-pilot-4'`), and the case counts
in §2 are the `guidance_rule_sources` rows each rule is bound to. **The
database was copied before the run** (`labcairn.db.backup.before-pilot4` and,
for the distillation, `pilot4-distil/labcairn.db.before-pilot4-rules`), so the
before state is recoverable.
