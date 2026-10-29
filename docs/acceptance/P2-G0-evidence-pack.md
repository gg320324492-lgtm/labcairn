# Phase 2, Gate 0 — the evidence pack

**Date:** 2026-10-29 · **Base commit:** `66dde87` · **Scope:** P2-G0 of the
Phase 2 execution design

**What this pack is.** The six things the Phase 2 execution design asks for
before any Phase 2 code is written, with the files that carry them and what
was actually measured. It is a report to the project owner, not a claim
that Phase 2 has begun.

**What this pack does not do.** It opens no ticket, migrates no table, and
writes no product code. **The two design documents asked for six things at
G0 and this pack delivers all six** — but every one of them is a document or
a measurement, and the six decisions in §5 are the owner's.

---

## 1. The six deliverables, and where they are

| The design asked for | Where it is | State |
|---|---|---|
| 1. the current state and a capability reuse matrix | [`docs/plans/PHASE_2-capability-reuse-matrix.md`](../plans/PHASE_2-capability-reuse-matrix.md) | 23 capabilities: 9 reuse, 8 extend, 6 cannot |
| 2. the A-level reference repos cloned, pinned and licensed | [`docs/research/upstream-study/`](../research/upstream-study/) | 6 clones, 6 SHAs, 6 records |
| 3. three ADRs | [ADR-0014](../adr/ADR-0014-paper-revision-provenance.md), [ADR-0015](../adr/ADR-0015-dataset-consent-and-access.md), [ADR-0016](../adr/ADR-0016-model-proposal-and-human-confirmation.md) | drafted, **not accepted** |
| 4. 20+ synthetic DOCX revision/comment negatives and a two-parser fidelity measurement | [`tests/docx_corpus.py`](../../tests/docx_corpus.py), [`tests/docx_fixtures.py`](../../tests/docx_fixtures.py), [`tests/test_docx_fixture_corpus.py`](../../tests/test_docx_fixture_corpus.py), [`tests/evaluation_docx_fidelity.py`](../../tests/evaluation_docx_fidelity.py) | 28 fixtures, 97 tests, measurement run |
| 5. new work orders and a file-ownership map | [`docs/plans/PHASE_2-mentor-trajectory-work-orders.md`](../plans/PHASE_2-mentor-trajectory-work-orders.md) | LC-P2-06 … LC-P2-14, and the map |
| 6. an end-to-end pilot plan | the same document, §4 and §7 | drafted |

**Nothing in PR #125 was changed.** The six tickets `LC-P2-00` … `LC-P2-05`
are untouched, their numbering is untouched, and the new tickets start at
`06`.

## 2. What the work established

### 2.1 Phase 1 left the exact slots Phase 2 needs, empty

The reuse matrix's most important finding is that the vocabulary for the
phase's central scientific claim **already exists and has never been used**:

- `EvidenceCreator.MODEL_PROPOSAL` (`evidence/states.py:112`) — declared,
  with a comment saying it "exists so a future proposal path is expressible"
  and never exercised. **A grep finds two hits: the declaration and the
  comment.**
- `EventType.OUTBOUND_CONSENT_REQUESTED` (`runtime/event.py:76`) —
  declared, never emitted.
- `VerificationStatus` is a **six**-state machine, not three, and its three
  negative states — `user_attested`, `conflicted`, `unsupported` — are
  exactly what a response-link model needs.
- `EvidenceRecord`'s constructor **already refuses** `user_attested` unless
  the creator is `USER`, with the reason in the error message: *"An
  attestation is something a person did; a rule or a model proposal
  reaching this state would misreport who stands behind the claim."*

**A phase that learns from revision histories without a way to say "this is
observed, this is inferred, this is a human's word" would be a phase that
cannot tell a measurement from a story.** Phase 1 built that distinction
and left the slot empty.

### 2.2 The gaps are structural, and three of them are named in the code

| Gap | Where | Consequence |
|---|---|---|
| `SourceKind` has **no DOCX** | `sources/source.py:88` | a Word file can be hashed but **not cited** |
| `LocatorKind` covers four kinds | `sources/locators.py:65` | a revision's anchor is a character range in a paragraph, which is none of them |
| `ApprovalRow` has no policy digest and no bound-source column | `db/models.py:415` | `consume` takes both **as arguments** (`recovery/approvals.py:216`), so a restart cannot check them from the row |
| `ArtifactLedger` is in memory | carried limitation | a rule a restart forgets is not a rule |
| the retrieval corpus is **three papers** | `tests/fixtures/retrieval/ground_truth.json` | `evidence-locator-validity` is `NOT MEASURED`, so LC-P2-11 has no measurement to be measured against |

**PR #125's LC-P2-02 claim was checked against the tree and is correct.**
The two missing columns are absent, the arguments are indeed passed in
rather than read, and the migration head is `0008_c2_profile`.

### 2.3 The fidelity measurement, and what it found

The measurement is in
[`docs/acceptance/LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md).
The corpus is 28 fixtures, 30 revisions, 8 deletions, 14 comments.

```
arm            rev found rev miss  rev rec cmt found cmt miss  cmt rec   del recov  accept ok  reject ok  attr
--------------------------------------------------------------------------------------------------------------
ooxml-native           0       30    0.000         0       14    0.000     0/8        0/28       0/28       no
pandoc                 0       30    0.000         0       14    0.000     0/8       26/28      28/28       no
python-docx            0       30    0.000         0       14    0.000     0/8       13/28      18/28       no
docx2python            0       30    0.000         6        8    0.429     0/8       23/28       9/28       no
```

**Four findings, each one a design decision made measurable:**

1. **No text arm reports a revision as an event.** Zero of thirty, for all
   three. A reader that produces text has nowhere to put "who did this" —
   which is why the OOXML-native reader has to be *written*, not configured.
2. **No arm recovers a deletion.** Zero of eight. The deleted text lives
   in `w:delText` and every text-producing reader reads `w:t`. **For a
   project whose thesis is "the deletion is the signal", this is the number
   that matters most, and it is zero.**
3. **pandoc silently drops a tracked insertion with no `w:author`.** The
   two fixtures differ in that attribute and in nothing else. A missing
   author is a reason to report `UNKNOWN`, not a reason to discard the
   edit — and the discard is invisible in the output.
4. **docx2python loses eight of fourteen comments, and one unpaired marker
   takes the whole set.** The precise trigger is the **count mismatch**,
   not the malformed marker: a comment whose marker is unpaired but whose
   count is balanced survives; one with no marker at all does not. Either
   way the anchor is lost, silently.

**A correction to the upstream study.** The docx2python record was written
from the source, which said the whole comment set disappears on any
mismatch. The measurement is more precise, and the precise version matters
for what the parser must do. The record has been updated.

### 2.4 The corpus found two of its own bugs

Both are worth recording, because they are what a synthetic corpus is for:

- The first version emitted the revision elements at the **front** of the
  paragraph, so pandoc's `accept` and `reject` modes gave the same text.
  A revision's position inside the paragraph is load-bearing.
- The first version carried **hand-written character offsets**, which
  pointed at a different part of the sentence than the revision's own text,
  so the fixture's accepted and rejected views were both nonsense.

**The second is the more important one: a hand-written expectation drifts
away from the thing it describes.** The offsets are now derived from the
text — a deletion names the baseline words it removes, an insertion names
the words it follows — and the writer **refuses** to build a fixture whose
anchor does not occur in its baseline.

## 3. The skills

**The user's instruction was to fetch the skills this project needs, and
quality rather than quantity.** What that turned out to mean:

- **The official marketplace holds 315 plugins, and not one of them is
  relevant.** They are SaaS integrations — Salesforce, HubSpot, Shopify,
  Notion, Atlassian — and the project touches none of them. Installing
  them would have been quantity.
- **The first-party `docx` skill is already on the machine**, shipped with
  the desktop app at
  `…/skills-plugin/…/skills/docx`. It is the single most relevant tool
  for LC-P2-07 and it was free.
- **Its capabilities are now understood, and they are not what LC-P2-07
  needs.** `comment.py` **generates** comments — which is exactly what a
  fixture builder wants — and `accept_changes.py` **accepts** revisions
  through a LibreOffice macro, which is a *destructive* transformation.
  There is **no fidelity reader**: the skill's "read content" path is
  `pandoc -t markdown`, and the measurement above shows what that yields.
  **ADR-0014 D6 forbids an "accept all revisions" operation on an
  original**, and the skill's script is the thing that rule is about.
- **The scientific skills already installed are relevant to the phase's
  later gates and were left alone**: `peer-review` (LC-P2-13),
  `scientific-writing` (LC-P2-12), `scientific-critical-thinking`
  (LC-P2-12's evidence grading), `citation-management` (LC-P2-04),
  `literature-review` and `research-lookup` (LC-P2-05 and the upstream
  studies), `experimental-design`, `statistical-analysis` and
  `statistical-power` (LC-P2-14's ablation design and its confidence
  intervals), `reproducibility-workflow` (the phase's provenance
  discipline), and `markitdown` (a third comparison parser, if LC-P2-07
  needs one).

**The dependencies that would have been wrong to add.** `docx2python` is
MIT and could be added — and was **not**, because a measurement tool that
adds its subjects to the product's dependency list changes the product it
measures. It runs through `uv run --with`, isolated. The same applies to
Docling, which was **read** but not installed: the deletion loss is
structural and is confirmed for the other three arms without it.

## 4. The reference repositories

Six clones, pinned, licences read from the files themselves. **Nothing was
copied, no weights were downloaded, no corpus was ingested.**

**Where they are.** `E:\labcairn-local\reference-repos\`, outside the
repository and on the E drive — the design's instruction is *"in a
dedicated directory outside the LabCairn repository; never `git init` inside
the project directory, and never add external source to LabCairn's Git
tree"*, and this is that, with the drive the project's own files live on.
The clones were made with `git clone --filter=blob:none`, so no blob was
fetched until a file was actually read, and no install script, container,
network service or model weight was touched.

| Project | SHA | Licence, read from the file | The finding |
|---|---|---|---|
| [arXivEdits](https://github.com/chaojiang06/arXivEdits) | `113913d6` | **none in the tree** | the README's licences are the *corpus's*, not the code's; the aligner requires CUDA and an unmaintained dependency |
| [XtraGPT](https://github.com/Xtra-Computing/XtraGPT) | `9f4be5c6` | **not established** | the README asserts MG0-2.0 and points at a `LICENSE` file **the repository does not ship** |
| [docx2python](https://github.com/ShayHill/docx2python) | `66b1ae3e` | MIT, verified | no `w:ins`/`w:del` anywhere in the tree |
| [Docling](https://github.com/docling-project/docling) | `8f7ae544` | MIT, verified | `msword_backend.py:2053` — a deleted run reads empty and is dropped |
| [PeerRead](https://github.com/allenai/PeerRead) | `9bb37751` | **none in the tree** | the corpus is drafts plus reviews with no stated terms; no *action* and no *outcome*, so no rule could be learned from it |
| [openreview-py](https://github.com/openreview/openreview-py) | `9e8ba8e6` | MIT, verified | the `forum`/`invitation`/`replyto` thread model is the review-loop shape; **no manuscript history**, and a client that can fetch a note can fetch a confidential one |

**Three of the six ship no licence file at all**, which is the design's
warning confirmed rather than assumed: *"克隆源码不等于获得代码复用权"*.

**The three that do ship a licence are permissive — and that is not why
none of the six is used.** docx2python and Docling are MIT, and openreview-py
is MIT too. Each is unused because of what it *cannot do*:

| Project | The property it fails |
|---|---|
| docx2python | reads no `w:ins`/`w:del` at all, and loses every comment when the range and element counts differ |
| Docling | a deleted run reads empty and is dropped, and its comment anchor is paragraph-granular |
| openreview-py | reaches other people's material, and has no manuscript history |
| arXivEdits | its aligner needs CUDA and an unmaintained dependency, and it ships no licence |
| XtraGPT | its weights' licence is asserted in prose and not shipped |
| PeerRead | it has no action and no outcome, so no rule could be learned from it |

**The finding that changes the phase's shape** is XtraGPT's. A model
trained on academic paper revision pairs **cannot claim that its advice
comes from the rule store** — it cannot report which parts of its behaviour
are learned and which are inherited. That is a scientific-integrity reason
to ground Phase 2's guidance in a citable, attributable rule store, and it
is independent of the licensing question.

## 5. The decisions that are the owner's

These are the ones this pack cannot make, and each one changes what happens
next.

### D1 — Is the mentor-trajectory line part of Phase 2?

**The roadmap's Phase 2 entry does not mention it.** Phase 2 is *"better
retrieval, citation identity/support, advanced analysis sandbox,
higher-fidelity plots, editing, expanded research Skills, conditional
reviewers/subagents"*. The trajectory line is none of those six. It is the
teacher's request, and it is **research** rather than a product feature, so
it may deserve its own phase.

**This pack does not assume the answer.** LC-P2-06 … LC-P2-14 are written
as a *supplement* to PR #125, not as a replacement, so either answer leaves
the six existing tickets standing.

### D2 — The pilot's deployment

**ADR-0015 D6 assumes a controlled single machine, an offline intake
directory, one administrator and a few invited annotators** — not a LAN
service and not a public one. The alternative needs a separate ADR for
identity and row-level access, and the conditions are written down.

### D3 — Which three to five papers enter the first pilot, and who arbitrates

**A person's decision, not a ticket's.** The corpus this line needs does
not exist yet.

### D4 — Whether the retrieval corpus is widened before the guidance agent

**The corpus is three papers and the locator-validity metric is
`NOT MEASURED`.** LC-P2-11's retrieval has no measurement to be measured
against until LC-P2-05 widens it, and LC-P2-14's ablation inherits the
ceiling.

### D5 — The numbering `LC-P2-06` … `LC-P2-14`

They are the numbers the two planning documents proposed, they are free
(PR #125 stops at `05`), and **this is the moment to change them** if
another scheme is preferred — after the first file lands, it is a rename
across three places.

### D6 — The CI shard cost for the new test file

**This is a mechanical consequence of adding a test file, and it needs a
runner.**

Adding `tests/test_docx_fixture_corpus.py` puts **two** of the repository's
own checks red, and they are red for the same reason and are fixed by
different means:

| The check | What it wants | How it is fixed |
|---|---|---|
| `tests/test_ci_shard_coverage.py::test_every_test_file_is_in_exactly_one_shard` | the file is in one of the CI shards | `make_ci_shards.py`, which **refuses to guess a cost** |
| `tests/test_ci_shard_coverage.py::test_the_recorded_costs_cover_every_test_file` | the file has a measured cost | a **runner's** number, not a local one |
| `tests/test_evaluation_harness.py::test_the_partition_files_every_test_file_exactly_once` | the file is filed in the evaluation protocol's partition | **done** — `tests/evaluation/manifest.py` files it under the repository class |

**The third one was found by running the suite, not by reading the rules**,
and it is worth recording because the two are different kinds of gap: the
partition is a **declaration** (which class a file belongs to), and a
declaration can be made from the tree — so it was made, and it is the only
existing file this work changed. The shard cost is a **measurement**, and a
measurement cannot be made from the tree.

**Getting a CI log needs a push or a pull request, and the owner decides
both.** The project's own precedent says this intermediate red is expected:
*"The board carried two red checks since this branch added
`test_application_evidence.py`, `test_event_payload_vocabulary.py` and
`test_real_provider_smoke.py` (no recorded cost)"* — and the costs were
supplied in a later, separate commit.

**What is needed:** the owner's word on whether to push or to open a pull
request for the measurement run. The file's local cost is 0.19 s and its
content is synthetic and fast, so the partition is not at risk; but the
number that goes in the table must come from a runner, and **this pack does
not write a locally-measured number into a table that says the numbers are
from runners.**

## 6. What is measured, and what is not

**Measured, and the numbers are in this pack:**

- **The whole suite, on the tree this pack was committed on**
  (`62bdea6`): **3783 passed, 5 skipped, 0 failed**, in 31 minutes 27
  seconds on this machine. The five skips are all of the project's own
  accepted kinds — a POSIX-only permission-bit case, the real-provider
  smoke that needs the owner's credential, and three Windows-path cases —
  and none of them is a new skip.
- The fidelity measurement on 28 fixtures, four arms, six dimensions
  (§2.3), run on this machine against the versions named in the
  acceptance record.
- The corpus's own 97 tests, green.
- The corpus is byte-reproducible, and the fixture writer refuses to build
  a fixture whose anchor does not occur in its baseline.
- `ruff check`, `ruff format --check` and `mypy --strict` are clean over
  the whole repository, 284 source files.

**The one check that is still red, and why it is red.** Adding the test
file puts `tests/test_ci_shard_coverage.py`'s two shard checks red: the
file is in no shard and has no recorded cost. **The cost must come from a
runner** (see D6), so this is a known, recorded, expected state — the
project's own precedent is the commit `9799354`, whose message says the
board *"carried two red checks since this branch added
`test_application_evidence.py`, `test_event_payload_vocabulary.py` and
`test_real_provider_smoke.py` (no recorded cost)"*, and which supplied the
costs in a later, separate commit.

**What the suite run also found**, which a reading of the rules would not
have: `tests/test_evaluation_harness.py::test_the_partition_files_every_test_file_exactly_once`
was **also** red, and it is a **declaration** rather than a measurement —
the evaluation protocol's partition must file every test file in a gate
class, or the file's cases enter no denominator. That one was fixed in
the tree (`tests/evaluation/manifest.py`), and it is the only existing
file this work changed.

**Not measured, and not claimed:**

- **No Phase 2 code exists.** No table migrated, no reader written, no
  agent built.
- **The guidance agent has never been shown to work.** LC-P2-14 exists to
  find out, and its acceptance explicitly allows the answer to be "no
  measurable gain".
- **No number here is about real Word documents.** The corpus is synthetic;
  ten real-world cases are listed in the corpus's `KNOWN_GAPS`.
- **Docling was read, not run.** Its own number is not measured, and this
  pack does not claim it.
- **The upstream repositories were read, not used.** No code copied, no
  weights downloaded, no corpus ingested.

## 7. The next step, if the owner says go

The order the work would take, with the dependencies as they are:

```
LC-P2-06  data governance ──┐
                            │  (a table, a migration, a set of refusals)
LC-P2-07  DOCX fidelity ────┘  (the reader, held to the measurement in §2.3)
   │
LC-P2-08  version graph
   │
LC-P2-09  feedback and response
   │
LC-P2-10  annotation and gold   ← this needs a person, not a code change
   │
LC-P2-11  the guidance memory
   │
LC-P2-12  the guided-revision agent   ← needs LC-P2-01's model path
   │
LC-P2-13  the peer-review loop
   │
LC-P2-14  blind evaluation and ablation
```

**LC-P2-10 is the one that cannot be parallelised**, and it is the one the
phase's scientific claim rests on. It needs two annotators and an arbiter,
and it needs the pilot corpus that D3 has to supply.

**The measurement in §2.3 is the acceptance test for LC-P2-07**, and it was
written before the reader for exactly that reason: a scoring function
written after the parser exists tends to score what the parser does.

## 8. The files this pack adds

| File | What it is |
|---|---|
| `docs/plans/PHASE_2-capability-reuse-matrix.md` | the reuse matrix |
| `docs/plans/PHASE_2-mentor-trajectory-work-orders.md` | LC-P2-06 … LC-P2-14, the dependency graph, the file-ownership map |
| `docs/adr/ADR-0014-paper-revision-provenance.md` | what a manuscript version is, and where a change is anchored |
| `docs/adr/ADR-0015-dataset-consent-and-access.md` | four permissions, not one |
| `docs/adr/ADR-0016-model-proposal-and-human-confirmation.md` | a proposal is a proposal |
| `docs/acceptance/LC-P2-07-fidelity-baseline.md` | the measurement and its findings |
| `docs/research/upstream-study/*.md` | four reference records |
| `tests/docx_corpus.py`, `tests/docx_fixtures.py` | the corpus and its gold |
| `tests/test_docx_fixture_corpus.py` | 97 tests on the corpus itself |
| `tests/evaluation_docx_fidelity.py` | the measurement |
| `tests/fixtures/README.md` | what the corpus is, why it is synthetic, and what it cannot reach |

**One existing file is changed:** `tests/evaluation/manifest.py`, which files
the new test file under the repository class. **That change is required**,
not a convenience — the partition test refuses a test file that is filed in
no class, because a file that is in no class has its cases in **no
denominator**, which is the hole the evaluation package exists to close.
It was found by running the suite, not by reading the rules.

**PR #125's six tickets are untouched.**
