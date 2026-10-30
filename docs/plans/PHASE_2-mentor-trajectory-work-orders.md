# Phase 2 — the mentor-trajectory work orders, as a supplement

**Status:** draft, written 2026-10-29 as the P2-G0 deliverable required by the
Phase 2 execution design. **Nothing here is dispatched**: no branch, no ADR
beyond the three drafts that accompany it, no board row.

**What this document is.** The second of the two Phase 2 work-order lists.
PR #125's `docs/plans/PHASE_2-work-orders-draft.md` holds six tickets,
`LC-P2-00` … `LC-P2-05`, in the order they have to happen. This one holds
**nine more, `LC-P2-06` … `LC-P2-14`**, covering the mentor-guidance
trajectory line: the teacher's request that the system learn *how a paper
is corrected*, not just what a finished paper says.

**What it does not do.** It does not touch PR #125's six tickets, and it does
not renumber them. It does not start work. It follows the Phase 1 pattern —
**a work order gets a task breakdown with a file-ownership map before code,
its acceptance clauses are written as clauses before the tests that carry
them, and a gate closes on an independent review at a named commit** — and it
stops at the point where the owner approves.

**The numbering.** `LC-P2-06` … `LC-P2-14` are the numbers the two external
planning documents proposed and the owner asked about. They are used here
because they are **free** — PR #125 stops at `05` — and because changing
them later would mean renumbering in three places. **The owner kept them on
2026-10-29**, and this line is now part of Phase 2 as an additional line
beside PR #125's six.

**The order the owner chose (2026-10-29).** LC-P2-08 first — the paper
project and the version graph — because LC-P2-06's grant table names the
paper project it covers, and because the reader's events have nowhere to
live until the tables exist. Then LC-P2-06, then LC-P2-09, then LC-P2-10,
which is the one that cannot be parallelised and needs people rather than
code.

---

## 1. The line, and what it is for

Phase 1's roadmap names Phase 2 as *"Scientific Intelligence: better
retrieval, citation identity/support, advanced analysis sandbox,
higher-fidelity scientific plots, editing, expanded research Skills,
conditional reviewers/subagents"*, with the exit gate *"measured capability
gain against a frozen P1 baseline, no scientific-claim inflation"*.

This line is **none of those six**, and that is deliberate. It is a
**research line** the teacher asked for: *让 Agent 学习一篇论文由初稿逐步修改成
可靠科研成果的过程* — the system should learn how a paper is corrected, not
what a finished paper looks like.

**Why it is not a violation of the phase.** The phase's exit gate is
"measured capability gain", and the reuse matrix
([`PHASE_2-capability-reuse-matrix.md`](PHASE_2-capability-reuse-matrix.md))
shows the line is built on Phase 1's own spine rather than beside it:

| What the line needs | What Phase 1 already has |
|---|---|
| a durable execution unit | Task / Run / Stage / Operation, with the crash-recovery semantics |
| a provenance vocabulary | the append-only event stream, closed and enforced by the database |
| an authorisation path | the capability registry, the approval ledger, the refusal vocabulary |
| an evidence vocabulary | `VerificationStatus` — **six** states, including `conflicted` and `unsupported` |
| a place for a model's say-so | `EvidenceCreator.MODEL_PROPOSAL` — **declared, never used** |
| an anchor for a claim | `SourceKind` / `LocatorKind` / `source_anchors`, with a resolving link check |

**The last two are the important ones.** Phase 1 left the exact slots this
line needs empty, on purpose. A system that learns from revision histories
without a way to say *"this is observed, this is inferred, this is a human's
word"* would be a system that cannot tell a measurement from a story, and
Phase 1's six-state evidence machine is that distinction, already built.

## 2. What the design documents asked for, and what is checked

The two planning documents propose the same nine tickets with slightly
different boundaries. This list keeps the substance and **corrects three
things the proposals got wrong**, each of which the reuse matrix or the
measurement established:

| The proposal | What the tree and the measurement say | Correction |
|---|---|---|
| *"LC-P2-08 跨版本内容对齐"* as a *diff* between extracted texts | the measurement shows no text arm recovers a deletion, and a diff of accepted text cannot distinguish a deletion from a rewrite | alignment runs over **revision events**, not over diffs of text — see LC-P2-08 |
| *"DOCX 批注解析"* as part of the same ticket as revisions | the measurement shows the two have **different failure modes**: comments can be lost wholesale by a count mismatch, revisions are lost by a text-node mismatch | they stay one ticket, because one reader produces both, but the **acceptance is two separate measurements** |
| a guidance agent that learns from the corpus | the upstream study of XtraGPT shows a model that already encodes unlabelled revisions **cannot claim its advice comes from the rule store** | the guidance path is **retrieval over a citable rule store** first; learning is LC-P2-15 and is optional |

## 3. The tickets

### LC-P2-06 — Data governance, consent and access

| | |
|---|---|
| **Objective** | The four independent permissions, the grant table, and the refusal paths that enforce them. |
| **Depends on** | ADR-0015 (drafted), and **LC-P2-08's `PaperProject` table** — the grant names the paper project it covers, so the table cannot be written before the thing it points at exists. |
| **Cost** | Medium: one table, one migration, one refusal vocabulary extension, one intake path. |
| **Acceptance** | Material with no grant is not readable for the restricted purpose; `external_transmit` and `train_reuse` are **denied by absence**; a grant naming provider A does not authorise provider B; withdrawing a grant invalidates the embeddings, index entries, cached transcripts and queued runs derived from it; `owner_id` authorises nothing; no real manuscript's bytes appear in the repository, in any CI artefact, or in the public evaluation corpus. |
| **Must not** | Model a data permission as an operation approval, or the two become one thing and the default-deny for transmission and training has no representation. |
| **Status** | **Implemented and measured**, 2026-10-29: `src/labcairn/security/permissions.py`, `src/labcairn/material/intake.py`, the two gates at `src/labcairn/application/model_transmit.py`, migration `0011_access_grants.py`, and 67 tests. **The ordering constraint held**: LC-P2-08's `PaperProject` table is in the tree (migration `0010`), so the grant table has something to point at. The fourteen acceptance clauses each have a named witness, and **seventeen mutations** were applied to prove those witnesses fail for their properties. The record is [`LC-P2-06-acceptance.md`](../acceptance/LC-P2-06-acceptance.md). |
| **Not yet done** | The **independent review**, which the owner's ruling of 2026-10-29 moves to after the merge; what it should break is already written down in [`PHASE_2-review-points.md`](PHASE_2-review-points.md). The **CI shard costs** for the six new test files were **apportioned first and are measured by the runner now**, and the partition they produce balances at **1.162** on Ubuntu and **1.000** on Windows. The **queues and indexes that hold the material** — the training queue, the embedding index, the derived corpus — are LC-P2-09's, so the exclusion of the material from them is not yet witnessed. **No grant has been issued and no model was called**: the grant-issuing rule is the owner's, and the two-gate path is built and tested rather than exercised. |
| **The ordering constraint, stated.** This ticket is written as *"depends on
  nothing"*, and that was wrong: `AccessGrant.subject_ref` names the paper
  project, so **LC-P2-08's `PaperProject` table has to exist first**. The
  two are otherwise independent, and the cheapest order is LC-P2-08's
  **table** first and LC-P2-06's **refusals** after it — the refusal paths
  do not need the table to be written, only to be *pointed at* something
  real. |

### LC-P2-07 — DOCX revision and comment fidelity

| | |
|---|---|
| **Objective** | The OOXML-native reader: `w:ins`, `w:del`, `w:moveFrom`, `w:moveTo`, `w:commentRangeStart/End`, `w:commentReference`, with authors, dates, anchors and the three views. |
| **Depends on** | ADR-0014 (drafted). **Not** on LC-P2-06, as the ticket originally said: the reader is a pure function over bytes and enforces no permission, so it can be written and measured before the consent table exists. LC-P2-06 governs **who may call it**, and the product path that calls it is where the two meet. |
| **Cost** | Large: a new adapter, a new `SourceKind`, a new `LocatorKind`, a migration, and the reader itself. |
| **Acceptance** | The measured target from [`LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md): **revision recall 1.0 and deletion recovery 1.0 on the synthetic corpus**; **comment recall 1.0**, with the four un-anchorable comments reported as `UNKNOWN` with a reason rather than dropped; the anchor is the comment's **range**, not the paragraph's; the original bytes are unchanged; a missing author or date is `UNKNOWN`, never guessed. |
| **Must not** | Extend the *report* revision model to manuscripts — the two answer different questions and the reuse matrix §4.1 says why. |
| **Status** | **Implemented and measured**, 2026-10-29: `src/labcairn/material/ooxml.py`, with `DocxLocator`, `SourceKind.DOCX`, migration `0009`, and 21 tests. Revision recall **30/30**, deletion recovery **8/8**, comment recall **14/14** on the synthetic corpus, and four mutations were applied to prove the witnesses fail for their properties. The record is [`LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md) §5. |
| **Not yet done** | The reader's behaviour on **real** Word documents — the corpus is synthetic, and the ten cases in its `KNOWN_GAPS` are the pilot corpus's job. The **store** side of the trajectory — the `PaperVersion` and `RevisionEvent` tables — is LC-P2-08's, and the reader's events are not persisted yet. |

### LC-P2-08 — Version graph and cross-version alignment

| | |
|---|---|
| **Objective** | `PaperVersion` as nodes, `VersionEdge` as directed edges, and the alignment that links a child version to its parent. |
| **Depends on** | LC-P2-07. |
| **Cost** | Large. |
| **Acceptance** | Two files with identical names and different bytes are two versions; a document with two parallel branches is representable and **no total order is implied**; an edge carries `source` (`evidence \| human \| model`), `confidence`, `evidence_spans` and `accepted_by`; **a version order is never inferred from a filename**; an unresolved relationship stays `UNRESOLVED` rather than being decided. |
| **Must not** | Use similarity alone to decide an edge, and never present a similarity score as a fact about the document's history. |
| **Status** | **Implemented and measured**, 2026-10-29: `paper_versions` and `version_edges` (migration `0010_paper_version_graph.py`), the contracts, the alignment that **proposes** an edge without deciding it, the human confirmation path, the duplicate and missing-round checks, and the exit demonstration — six test files, and **the whole suite green** (3894 passed, 5 skipped, 0 failed, in 34 minutes 56 seconds) on the tree at `ef1a36c`. The record is [`LC-P2-08-acceptance.md`](../acceptance/LC-P2-08-acceptance.md). |
| **Not yet done** | The **independent review**, which the owner's ruling of 2026-10-29 moves to after the merge. **LC-P2-07's reader produces the revision events these tables hold, and nothing writes them into the store yet**: the reader exists, the store exists, and the seam between them is not wired — so the version graph is presently fed by hand. |

### LC-P2-09 — Feedback, response and follow-up

| | |
|---|---|
| **Objective** | `FeedbackEvent`, `EditAction`, `ResponseLink`, `FollowupAssessment` — the chain *问题 → 指导意见 → 修改行动 → 修改后的证据 → 后续评价*. |
| **Depends on** | LC-P2-08. |
| **Cost** | Large. |
| **Acceptance** | A comment is clickable through to its anchor, the change it prompted, and the later outcome; **an unaddressed comment is not reported as addressed**, and neither is a wrong response or a partial one; a round in which the same issue recurs is visible as a recurrence rather than as two unrelated comments; the response state names **what evidence** decided it. |
| **Must not** | Assert *"the advisor was right"* because the student's change was accepted — the design's §4.2 and the acceptance clause both forbid it. |
| **Status** | **Designed, not dispatched.** [`ADR-0017`](../adr/ADR-0017-feedback-chain.md) and [`LC-P2-09-task-breakdown.md`](LC-P2-09-task-breakdown.md) were written on 2026-10-30: the four tables, the three decisions that shape them (a feedback is an observation with two addresses; a response is a judgement with evidence behind it; *"the change was accepted"* is not *"the advisor was right"*), and sixteen acceptance clauses. **Two gaps in the tree are recorded rather than assumed.** The DOCX reader's anchored text is **always empty** — `CommentAnchor.text` is `""` on every path — so the chain's first link has no content; and `paper_versions` and `version_edges` have **no writer at all**, so an edit would have nothing to name, which is why the version graph's writer is the first subtask rather than an afterthought. The design also records that **"a round" is a document and not a new entity**, and that a recurrence is an `issue_key` somebody gives rather than a similarity the system infers. |

### LC-P2-10 — Process annotation and the gold set

| | |
|---|---|
| **Objective** | The label set, the annotation guide, and a small human-annotated gold set. |
| **Depends on** | LC-P2-09; runs **in parallel** with LC-P2-06. |
| **Cost** | Labour, not compute. **This is a person's time and it is the scarcest resource in the phase.** |
| **Acceptance** | A published label guide; a gold set with two independent annotators and an arbiter; inter-annotator agreement reported with its denominator; `UNKNOWN` is a label and not a failure; **the split is by `PaperProject`, never by event** — every version of a paper is in the same partition. |
| **Must not** | Import a taxonomy from a paper and call it Phase 2's. The arXivEdits study says why: its classes describe *what kind of text edit* was made, which is a different axis from *what problem the advisor pointed at*. |

**Task breakdown:** [`LC-P2-10-task-breakdown.md`](LC-P2-10-task-breakdown.md),
written 2026-10-30. **Half of it is a person's job**: T00–T05 are dispatchable
as code and documents, and **T06 is two annotators and an arbiter filling the
manifest** — the work order is not done until that block exists.

### LC-P2-11 — The mentor guidance memory

| | |
|---|---|
| **Objective** | `GuidanceRule` — a candidate, a rule, a counterexample, a retraction — and the retrieval over it. |
| **Depends on** | LC-P2-09, LC-P2-10; reads LC-P2-04 and LC-P2-05's retrieval. |
| **Cost** | Large. |
| **Acceptance** | Every retrieved rule reaches a **real comment and a real before/after difference**; a rule's source material withdrawn **invalidates the rule**; a counterexample stops the rule being served unconditionally; **two conflicting rules are both returned and neither wins by being newer**. |
| **Must not** | Store *"an advisor prefers this style"*. Every rule has a problem, a context, a scope, a counterexample and a version. |

### LC-P2-12 — The guided-revision agent

| | |
|---|---|
| **Objective** | `GuidanceCard`: a diagnosis, an anchor, an explanation, a next step, the evidence and the counterexamples, the uncertainty, and what needs the student's confirmation. |
| **Depends on** | LC-P2-01, LC-P2-02, LC-P2-06 … LC-P2-11. |
| **Cost** | Large, **and it spends money** — the owner's authorisation is a precondition. |
| **Acceptance** | A card carries an anchor into the current manuscript; **insufficient material produces an abstention record naming what was missing**, not an empty result; no card invents an experiment, a reference or an advisor's opinion; a card cites a rule **with its counterexamples**; a human can accept or reject a card and the decision is audited; **the model cannot modify a manuscript, create an artefact without consent, or execute code**. |
| **Must not** | Let a model proposal become a verified record. ADR-0016's D2: the record model already refuses `user_attested` for a non-`USER` creator, and Phase 2's path must not bypass that by writing the creator field itself. |

### LC-P2-13 — The peer-review loop

| | |
|---|---|
| **Objective** | `ReviewerComment → AuthorResponse → RevisionEvidence → NextReview`, across first and second rounds. |
| **Depends on** | LC-P2-09 … LC-P2-12. |
| **Cost** | Medium-large. |
| **Acceptance** | A review point is located in the response and in the actual change; **a response that claims an experiment the manuscript does not contain is not marked done** — that is the negative case the design names, and it is the one a model is most likely to get wrong; an unanswered point stays unanswered; a conflict between an advisor's view and a reviewer's is **shown as two sides**, not resolved by recency. |
| **Must not** | Treat acceptance as proof that the advice was scientifically right. |

### LC-P2-14 — Blind evaluation and ablation

| | |
|---|---|
| **Objective** | The scientific acceptance: does process learning beat final-text-only, and is the gain real? |
| **Depends on** | A minimal vertical slice of LC-P2-07 … LC-P2-13. |
| **Cost** | **The most expensive thing in the phase**: human blind rating plus the cost of five arms' worth of model calls. |
| **Acceptance** | A frozen evaluation set, split **by paper**; five arms (A: current draft + general model; B: + ordinary literature RAG; C: + version differences; D: + advisor comments and student responses; E: + review outcomes and confirmed rules) on the **same underlying model and a comparable budget**; the two contrasts that matter — **D vs C** and **E vs D** — are measured; the sample size, the confidence intervals and the failure cases are reported; **if the gain is not significant, that is reported as not significant**. |
| **Must not** | Train on a paper and evaluate on its own final version. The split is by project, and the leak check is a test. |

### LC-P2-15 (optional, not a Phase 2 deliverable) — Strategy optimisation

Prompt optimisation or a small amount of fine-tuning, **only after**
LC-P2-14 has established that the sample size, the consent, the data quality
and the gain are all sound. A separate approval, on its own ticket. It is
not on the critical path and nothing in this line waits for it.

## 4. The dependency graph

```
LC-P2-00 (PR #125)  freeze the baseline
        │
LC-P2-02 (PR #125)  restart-durable consent
        │
LC-P2-01 (PR #125)  the model-call path
        │
        ├──────────────┐
        │              │
LC-P2-04, LC-P2-05   │  citation identity, retrieval quality
        │              │
        └──────┬───────┘
               │
LC-P2-06  data governance ──────────┐
        │                            │
LC-P2-07  DOCX fidelity              │
        │                            │
LC-P2-08  version graph              │
        │                            │
LC-P2-09  feedback and response      │
        │                            │
LC-P2-10  annotation and gold ◄──────┘  (runs in parallel with LC-P2-06)
        │
LC-P2-11  the guidance memory
        │
LC-P2-12  the guided-revision agent
        │
LC-P2-13  the peer-review loop
        │
LC-P2-14  blind evaluation and ablation
```

**Two things can start now, and they do not touch each other:** LC-P2-06
(data governance — a table and a set of refusals) and LC-P2-07's *fixture
corpus*, which exists already. **Nothing in the mentor line may start
before LC-P2-06**, because a document that may not be parsed is a document
that may not be stored, and the consent has to come first.

## 5. The file-ownership map

**The rule.** Each ticket owns its files outright. A ticket that needs
another's file says so in its task breakdown rather than reaching for it.
**The two existing Phase 1 files every ticket touches are listed, and
touching them is a declared dependency, not a convenience.**

| Ticket | Files it owns (new unless stated) | Phase 1 files it touches |
|---|---|---|
| LC-P2-06 | `src/labcairn/security/consent.py` (new), `src/labcairn/db/models.py` (**grant rows**), `src/labcairn/db/migrations.py` (**migration 0009**), `src/labcairn/security/capabilities.py` (**new capability ids**), `tests/test_dataset_consent.py` (new) | `db/models.py`, `db/migrations.py`, `security/capabilities.py` |
| LC-P2-07 | **done**: `src/labcairn/material/ooxml.py`, `src/labcairn/sources/locators.py` (**new locator kind**), `src/labcairn/sources/source.py` (**new source kind**), `src/labcairn/material/addressing.py` (**new locator fields**), `src/labcairn/material/ingest.py` (**extension map**), `src/labcairn/material/__init__.py` (**registration**), `migrations/versions/0009_docx_locator.py` (**migration**), `db/models.py` (**the new columns and constraints**), `tests/test_ooxml_revisions.py` | as above, plus `tests/test_source_contracts.py` (**the closed sets moved**) |
| LC-P2-08 | `src/labcairn/papers/versions.py` (new), `src/labcairn/papers/alignment.py` (new), `tests/test_version_graph.py` (new) | `db/models.py` (new tables), `db/migrations.py` |
| LC-P2-09 | `src/labcairn/papers/feedback.py` (new), `tests/test_feedback_response.py` (new) | `db/models.py`, `db/migrations.py` |
| LC-P2-10 | `docs/papers/annotation-guide.md` (new), `docs/papers/gold-set-manifest.json` (new), `tests/fixtures/papers-gold/` (new) | — |
| LC-P2-11 | `src/labcairn/papers/rules.py` (new), `src/labcairn/papers/retrieval.py` (new), `tests/test_guidance_rules.py` (new) | `db/models.py`, `db/migrations.py`, `evidence/index.py` |
| LC-P2-12 | `src/labcairn/papers/guidance.py` (new), `src/labcairn/application/guidance.py` (new), `tests/test_guidance_cards.py` (new) | `application/` (the layer), `evidence/record.py`, `security/capabilities.py` |
| LC-P2-13 | `src/labcairn/papers/review.py` (new), `tests/test_review_loop.py` (new) | `db/models.py`, `db/migrations.py` |
| LC-P2-14 | `tests/evaluation_trajectory.py` (new), `docs/acceptance/LC-P2-14-*.md` (new) | `tests/evaluation/` (the harness) |

**The `db/models.py` and `db/migrations.py` columns are the reason this
list exists.** Six of the nine tickets add tables, and six tickets editing
one file is six chances to collide. The rule is that **each ticket's
migration is its own numbered file**, and the migration list is appended to
in ticket order — so LC-P2-06 writes `0009`, LC-P2-08 writes `0010`,
LC-P2-09 writes `0011`, and so on. The schema parity test
(`tests/test_evidence_schema.py`, which walks `Base.metadata` and the
migrated schema independently) is what catches a table added to one and not
the other.

**The shared directories.** `src/labcairn/papers/` is **new** and belongs to
this line. It is not a sub-package of `sources/` (that package is about
material, and a version is not a material) and not of `evidence/` (that
package is about claims, and a version is not a claim). If the owner prefers
a different home, it is a rename before the first file lands, not after.

## 6. What has to be decided before the first code

**The owner decides, not this list.** Four things:

1. **Is the mentor-trajectory line part of Phase 2?** The roadmap's Phase 2
   entry does not mention it. It is the teacher's request, and it is
   research rather than a product feature, so it may deserve its own
   phase. **This document does not assume the answer.**
2. **The pilot's deployment.** A controlled single machine with invited
   annotators, or a shared server. ADR-0015 D6 assumes the former and
   records the conditions the latter would need.
3. **Which three to five papers enter the first pilot**, and who arbitrates
   the annotation conflicts. That is a person's decision, not a ticket's.
4. **Whether the retrieval corpus is widened before the guidance agent is
   built.** The reuse matrix §3.7 records that the corpus is **three
   papers** and that the locator-validity metric is `NOT MEASURED` — so
   LC-P2-11's retrieval has no measurement to be measured against until
   LC-P2-05 widens it.

## 7. What is already true, and what is not

**True, and checked:**

- The six A-level reference repositories are cloned, pinned by SHA, and
  their licences read from the files themselves —
  [`docs/research/upstream-study/`](../research/upstream-study/).
- The reuse matrix names every existing capability Phase 2 builds on, with
  file, line, test and commit —
  [`PHASE_2-capability-reuse-matrix.md`](PHASE_2-capability-reuse-matrix.md).
- Three ADRs are drafted —
  [ADR-0014](../adr/ADR-0014-paper-revision-provenance.md),
  [ADR-0015](../adr/ADR-0015-dataset-consent-and-access.md),
  [ADR-0016](../adr/ADR-0016-model-proposal-and-human-confirmation.md).
- The synthetic corpus of 28 DOCX fixtures and its gold exist, and 97 tests
  check the corpus itself —
  `tests/docx_corpus.py`, `tests/docx_fixtures.py`, `tests/test_docx_fixture_corpus.py`.
- The fidelity measurement runs and produces the baseline the reader will
  be held to —
  [`LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md).

**Not true, and not claimed:**

- **The trajectory's own tables do not exist.** No `PaperProject`, no
  `PaperVersion`, no `RevisionEvent` — those are LC-P2-06, LC-P2-08 and
  LC-P2-09. **One migration has landed** (`0009_docx_locator`), and it
  makes a DOCX addressable; it adds no trajectory table.
- **The reader is written; the reader is not yet fed by the product.** It
  reads a document's history correctly on the synthetic corpus, and its
  events are **not persisted**, because the tables they would live in are
  LC-P2-08's.
- **The guidance agent has never been shown to work**, and nothing in this
  list says it will. LC-P2-14 exists to find out, and its acceptance
  explicitly allows the answer to be "no measurable gain".
- The upstream repositories were **read, not used**. No code was copied, no
  weights downloaded, no corpus ingested. **Three of the six ship no licence
  file at all** — arXivEdits, XtraGPT and PeerRead — and the licences that
  do ship are permissive. Neither fact is why none of the six is used: each
  fails a property the phase needs, and each failure is recorded in its own
  study.
  file at all.
- The corpora this line will need — advisor comments, student responses,
  review outcomes — **do not exist yet** and need the pilot, which needs
  the owner's decisions in §6.
