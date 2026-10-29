# LC-P2-08 — Paper projects and the version graph: task breakdown

**Status:** ready to implement. Detailed decomposition only — nothing here is
implemented, and this document does not authorise starting without the
owner's go-ahead.
**Subject when written:** `claude/phase2-g0` @ `c5d22b6` (PR #126)
**Date:** 2026-10-29
**Gate:** the first gate of the mentor-trajectory line (P2-G1).
**Ordered by the owner, 2026-10-29:** LC-P2-08 comes before LC-P2-06,
because LC-P2-06's grant table names the paper project it covers, and
because **a revision event that nothing can store is a reading and not a
record**.

## 0. How to read this document

Section 1 fixes what is in and out. Section 2 describes the shape of the
thing being built, because three decisions in it are load-bearing and easier
to reason about in one place than spread across the subtasks. Section 3 is
the work, in dependency order, with a file-ownership map. Section 4 maps the
acceptance clauses onto the subtask and test that carries each one. Section 5
records what this work order cannot deliver, and why.

Every claim about what "cannot" happen is a refusal or a state, never an
absence. That is the project's standing rule, and here it has a specific
consequence: **an unresolved version relationship is a first-class value**,
not a missing row and not an order that was guessed.

## 1. Goals and boundaries

### 1.1 What LC-P2-08 must produce

From the work order: *a paper project is a body of material about one
manuscript; versions are nodes in a graph rather than a list; the alignment
between a child version and its parent is evidence with a confidence and a
human arbiter, and the order is never inferred from a file name.*

Concretely, by the end:

1. A **`paper_projects` table** — one row per manuscript, holding the
   workspace it lives in, the consent reference that permits it, and the
   pseudonym under which it is stored.
2. A **`paper_versions` table** — one row per version, naming the source
   file it came from, the label the author gave it, and the **candidate
   stage** the system inferred (draft, advisor-reviewed, submitted,
   camera-ready, unknown).
3. A **`version_edges` table** — a directed edge from a parent version to a
   child, carrying **how** the relationship was decided (`evidence | human |
   model`), a confidence, the evidence that supports it, and who accepted it.
4. An **alignment** that links a child version to its parent **by evidence**
   — shared structure, shared headings, matching passages, matching numbers —
   and that **refuses to decide** when the evidence does not point one way.
5. A **human confirmation path**, so that an edge the system inferred can be
   accepted, corrected or rejected, and **the correction is a new version of
   the edge rather than an overwrite**.
6. A **duplicate and missing-round check**, so that two files with the same
   name and different bytes are two versions, and a gap in the sequence is
   visible.

### 1.2 Already done — removed from scope

- **Reading a Word document's revisions and comments.** LC-P2-07's reader
  exists and is measured
  ([`LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md)):
  revision recall 30/30, deletion recovery 8/8, comment recall 14/14. This
  work order **stores** what that reader produces; it does not re-read it.
- **The DOCX address.** `DocxLocator` names a package part, an element path,
  a view and a character range, and it is in the store's vocabulary
  (migration `0009_docx_locator`). This work order uses it and does not
  widen it.
- **The consent table.** LC-P2-06 owns `access_grants`, and it depends on
  *this* work order's `paper_projects`. This work order therefore **does
  not** decide whether a material may be read — it records the consent
  **reference** that LC-P2-06 will fill in, and a project with no grant is
  **readable as a project and unreadable as material**. The two are
  different states, and the difference is the point.
- **The application layer, the CLI and the API.** A project is a record, and
  the surfaces that show it are LC-P2-12's work.

### 1.3 Explicitly not in scope

- **Any model call.** Nothing here asks a model anything. The alignment is
  rules and evidence.
- **Any outbound transmission.** No material leaves the machine in this work
  order.
- **A decided version order.** The system proposes; a person disposes.
- **The mentor experience store.** LC-P2-11's rules are built on the cases
  this work order makes addressable; it does not build them.
- **The response links.** LC-P2-09 owns `feedback → edit → response →
  outcome`; this work order owns *which text a change happened to*.

## 2. The three decisions that shape it

### 2.1 A version graph, never a version list

**The teacher's process contains parallel branches.** A student sent two
different revised drafts; the advisor replied to both. A chain cannot
represent that, and a chain would force the system to invent an order it does
not have.

So `paper_versions` is a set of nodes and `version_edges` is a set of
directed edges. **There is no `parent_id` column on the version**, because a
column that holds one parent cannot hold two, and the branch is the case the
design names.

### 2.2 The edge carries how it was decided, and the confidence is not the decision

An edge says three separate things:

| Field | What it is |
|---|---|
| `source` | `evidence`, `human` or `model` — **how** the relationship was established |
| `confidence` | how strong the evidence is — **a number**, and not a decision |
| `accepted_by` | **who** accepted it, and it is `None` until a person does |

**The design's rule: "禁止仅靠相似度静默确定版本顺序"** — a similarity
score may never silently decide an order. So an `evidence` edge with a high
confidence is still **unaccepted**, and the version graph reports it as a
proposal. A `human` edge is accepted, and it records who.

**A file name is never evidence of order.** `最终版2.docx` is not newer than
`投稿版.docx`; the design says so outright, and the file's mtime is not
evidence either — a copied file carries the copy's time.

### 2.3 An unresolved relationship is a value, not an absence

The design's rule: *"不确定时 `UNRESOLVED` + 人工确认"*. So a version whose
parent is not established has a **`status` of `UNRESOLVED`**, and it is
**listed** — the gap in the sequence is the thing the user most needs to see.

**The tempting alternative is to leave the edge out**, so that the graph has
no dangling node. That is worse: the version exists, it is material in the
project, and hiding it because its parent is unknown makes the archive look
complete when it is not.

## 3. The work

### T00 — The schema, and the decision to write it

**Files:** `src/labcairn/db/models.py`, `migrations/versions/0010_paper_version_graph.py`,
`tests/test_store_migrations.py`.

**The tables.**

```
paper_projects:
  project_id           the caller-minted identity
  workspace_id         the workspace the material lives in
  subject_pseudonym    a pseudonym; the name is held separately (ADR-0015 D5)
  consent_ref         the reference LC-P2-06 will resolve; None means "no grant"
  created_at

paper_versions:
  version_id
  project_id          -> paper_projects
  source_id           -> sources (the ingested file)
  version_label_raw   the label the author's file name gave, kept verbatim
  stage_candidate     draft | advisor_reviewed | submitted | camera_ready | unknown
  status              resolved | unresolved
  created_at

version_edges:
  edge_id
  parent_version_id   -> paper_versions
  child_version_id    -> paper_versions
  source              evidence | human | model
  confidence          0..1, the strength of the evidence
  evidence_spans      what supports the edge
  accepted_by         the person who accepted it; None while unaccepted
  accepted_at
  version             the edge's own revision number, for corrections
```

**Two constraints the schema holds, and they are the point.**

1. **A parent is not a column on the version** (§2.1).
2. **An edge's `accepted_by` is `NULL` until a person accepts it**, and the
   schema says so. A row that claims an acceptance with no actor is refused
   — the same rule ADR-0004's record model applies to an attestation.

**And the one that is a trap.** `confidence` is a number and `accepted_by`
is a decision. **A check constraint that requires `accepted_by IS NOT NULL`
whenever `source = 'evidence'` would make the system unable to record a
proposal at all** — which is the opposite of what the design wants. The
constraint is the other way round: an edge that **claims** to be accepted
must name **who** accepted it, and an edge with no acceptor is simply
unaccepted.

**Note on the migration number.** `0009_docx_locator` is LC-P2-07's, and it
is on the branch but not yet merged. **This work order's migration is `0010`**
because the revisions are sequential and the branch is what merges. If
LC-P2-07's migration is renumbered before the merge, this one moves with it.

**The acceptance is that the migration and the ORM agree**, which
`tests/test_evidence_schema.py`'s parity test checks by walking
`Base.metadata` and the migrated schema independently. **And that a row the
schema must refuse is refused** — the project's own lesson from revision
0007 is that *"a test comparing two texts cannot catch both being wrong"*,
and only writing a row that must be refused catches it.

### T01 — The version and edge records, as typed models

**Files:** `src/labcairn/papers/versions.py` (new), `tests/test_version_graph.py`.

**The models** are Pydantic and frozen, like every other contract in the
project: `PaperProject`, `PaperVersion`, `VersionEdge`.

**The edge's type is the interesting one.** It must express:

- a proposal (`source='evidence'`, `accepted_by=None`);
- an acceptance (`source='human'`, `accepted_by='somebody'`);
- a correction (the same edge, `version` incremented, with the correction's
  own evidence and acceptor).

**And it must refuse the combinations that lie.** An edge with
`source='human'` and no `accepted_by` is a **human decision with nobody
behind it** — refused. An edge with `accepted_by` set and `source='evidence'`
is a **machine proposal wearing a person's name** — refused.

**A second refusal: an edge whose `confidence` is outside 0..1**, and an
edge with `parent_version_id == child_version_id**, which is not a
self-loop to be tolerated but a contradiction.

### T02 — The alignment: evidence, and the refusal to decide

**Files:** `src/labcairn/papers/alignment.py` (new), `tests/test_version_alignment.py`.

**The evidence, in the order it is trusted.**

1. **Shared structure.** Headings that match, in the same order, at the same
   level — a strong signal that two files are versions of one paper.
2. **Matching passages.** The paragraph-level alignment LC-P2-07's line
   alignment gives, or a simpler one here: a substantial passage that
   appears in both, in the same relative position.
3. **Matching numbers.** The same experimental result in both — a strong
   signal, and one the design names (*"图表数字变化但文字不变"*).
4. **Nothing else.** Not the file name, not the mtime, not the file size.

**The refusal.** When two versions share their structure but the evidence
points two ways — the passage order differs, the numbers disagree about
which is later — the alignment **does not decide**. It emits a
**candidate set** with the evidence for and against, and the versions stay
`UNRESOLVED`.

**And the number-only case is its own test**, because it is the one a
similarity method gets wrong: two drafts whose prose is nearly identical and
whose **results differ** are two versions, and the difference is the
scientific content. A similarity threshold would score them as *the same
version*.

### T03 — The human confirmation path

**Files:** `src/labcairn/papers/versions.py`, `tests/test_version_confirmation.py`.

A person sees the proposed edge, the evidence for it, the evidence against
it, and the two versions' texts. They **accept**, **correct** (naming the
parent they meant) or **reject** it.

**A correction is a new version of the edge, not an overwrite.** The
project's rule is that a human revision produces a new version rather than
silently replacing what was there, and the edge table carries `version` and
`accepted_by` for exactly this. The previous edge stays readable.

**The refusal:** an acceptance that names nobody, and a correction that
names a version outside the project.

### T04 — The duplicate and missing-round checks

**Files:** `src/labcairn/papers/versions.py`, `tests/test_version_duplicates.py`.

Two checks, and both are about **not lying**:

1. **Duplicates.** Two files with the **same name and different bytes** are
   two versions — or one version and one copy. The system cannot tell, and
   says so: it records both, marks the relationship `UNRESOLVED`, and the
   duplicate check **reports** it rather than resolving it.
   **Two files with the same name and the same bytes are one version** —
   the content hash decides that, and it is the one thing here that is
   decided by evidence rather than by a person.
2. **Missing rounds.** A project whose versions are v1, v2 and v4 has a
   **gap**. The system does not invent a v3 and does not renumber: it
   records that the sequence has a hole, because a missing round is
   information the owner needs — a version may have been lost, or it may
   never have existed.

### T05 — The end-to-end demonstration

**Files:** `examples/paper_version_demo.py`, `tests/test_paper_version_demo.py`.

**A demonstration is run by a test.** The project's rule, from LC-P1-10's
T10: *"unlike the earlier exit demonstrations, this one is run by a test — a
demonstration nobody runs is one that quietly stops working."*

The demonstration: a project with four versions, one of which has **no
established parent**, one pair of which are **duplicates by name**, and one
edge the alignment **proposes and a person accepts**. It prints the graph,
the unresolved relationship, the duplicate report and the accepted edge, and
the test asserts every one of them.

### T06 — What the tables cost, and the file-ownership map

**Files:** `docs/acceptance/LC-P2-08-acceptance.md` (the record, at the
end).

The shard-cost rule applies here: **a new test file changes the CI
partition's balance**, and the cost must come from a runner. See
§5.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The subtask | The test |
|---|---|---|---|
| A1 | Two files with the same name and different bytes are **two versions**, not one | T04 | `test_two_files_with_the_same_name_and_different_bytes_are_two_versions` |
| A2 | Two files with the same name and the same bytes are **one version** | T04 | `test_the_same_bytes_are_one_version_whatever_the_name` |
| A3 | A version with no established parent is `UNRESOLVED` and is **listed** | T00, T02 | `test_a_version_with_no_established_parent_is_unresolved_and_listed` |
| A4 | **The order is never taken from a file name** | T02 | `test_a_file_name_never_decides_the_order` |
| A5 | **The order is never taken from an mtime** | T02 | `test_a_modification_time_never_decides_the_order` |
| A6 | A proposal with high confidence is still **unaccepted** until a person accepts it | T01 | `test_a_confident_proposal_is_still_unaccepted` |
| A7 | An edge claiming a human decision with **no acceptor** is refused | T00, T01 | `test_an_edge_with_no_acceptor_is_refused` |
| A8 | An edge with `source='evidence'` and an `accepted_by` is refused | T01 | `test_a_proposal_wearing_a_persons_name_is_refused` |
| A9 | The alignment **refuses to decide** when the evidence points two ways | T02 | `test_the_alignment_refuses_when_the_evidence_points_two_ways` |
| A10 | Two drafts whose prose matches and whose **numbers differ** are two versions | T02 | `test_two_drafts_that_differ_only_in_their_results_are_two_versions` |
| A11 | A missing round is **reported**, and no version is invented | T04 | `test_a_missing_round_is_reported_and_nothing_is_invented` |
| A12 | A correction is a **new version of the edge**, and the old one stays readable | T03 | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` |
| A13 | An edge whose parent is outside the project is refused | T03 | `test_an_edge_to_a_version_outside_the_project_is_refused` |
| A14 | The demo is run by a test | T05 | `test_the_paper_version_demo_runs` |

**And the negative cases the design names**, each of which is a clause above
rather than an extra one: *"同名文件、缺失版本、同一论文平行分支、误放另一论文、
伪造日期、压缩包路径穿越、zip bomb、恶意宏（不执行）、同名不同字节、哈希一致
不同名"*. Of those, the ones this work order owns are the duplicates
(A1, A2), the missing round (A11), the parallel branch (A3) and the
**misfiled other paper** — which is T02's job to *not* decide: two files that
share structure but are different papers must stay two projects, and the
alignment has no way to merge projects.

**The zip bomb, the path traversal and the macro are not this work order's.**
They belong to whatever ingests the intake archive, and they are listed in
§5 so they are not forgotten.

## 5. What this work order cannot deliver, and why

- **It does not decide which material belongs to which paper.** That is the
  clustering problem, and the design puts it in the same ticket as the
  archive. The difference matters: **a version's *parent* is a question
  about history, and a version's *project* is a question about identity**,
  and the second is harder and needs the human. This work order makes the
  parent decidable by evidence and the project **declarable by a person**.
- **It does not read a PDF.** A PDF has no revision history; it is a
  version of a paper and nothing more. It enters as a source with no
  revisions.
- **It does not ingest an intake archive.** The design's §7 names the zip
  bomb, the path traversal and the macro. **None of those is a version-graph
  question**, and putting them here would make this work order about
  untrusted archives. They belong to the intake path — which is LC-P2-06's,
  because intake is where a grant is checked.
- **It does not persist LC-P2-07's revision events.** It stores the
  **versions and their relationships**. The events themselves — who wrote
  what, with what author and date — are LC-P2-09's `EditAction`, because
  an edit action is a *response* to a piece of feedback, and this work
  order does not know about feedback. **What this work order stores is
  where a version came from; what LC-P2-09 stores is what happened inside
  one.**
- **It does not decide anything a person must decide.** Every "I do not
  know" in this work order is a recorded state.

## 6. The file-ownership map

**Each subtask owns its files outright.** A subtask that needs another's file
says so here rather than reaching for it.

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | `migrations/versions/0010_paper_version_graph.py` | `src/labcairn/db/models.py` |
| T01 | `src/labcairn/papers/__init__.py`, `src/labcairn/papers/versions.py`, `tests/test_version_graph.py` | — |
| T02 | `src/labcairn/papers/alignment.py`, `tests/test_version_alignment.py` | `src/labcairn/papers/versions.py` (its own) |
| T03 | — | `src/labcairn/papers/versions.py` (its own), `tests/test_version_confirmation.py` (new) |
| T04 | — | `src/labcairn/papers/versions.py` (its own), `tests/test_version_duplicates.py` (new) |
| T05 | `examples/paper_version_demo.py`, `tests/test_paper_version_demo.py` | — |
| T06 | `docs/acceptance/LC-P2-08-acceptance.md` | — |

**The two shared files, and why they are shared.**

`src/labcairn/db/models.py` is shared because every table in the project
lives in it, and the migration parity test compares it against the migrated
schema. **Only T00 writes to it**, and the other subtasks take their tables
as given.

`src/labcairn/papers/versions.py` is shared because T02, T03 and T04 all
extend it. **T01 writes it; the others extend it.** That is a real collision
risk, and the resolution is that these subtasks are **sequential by
construction**: T02 cannot start before T01's version of the file is
settled, and T03 and T04 both follow T02.

**And the migration sequence.** `0010` follows `0009` (LC-P2-07's). The
project's rule is one migration per work order, numbered in order, and the
parity test catches a table added to one and not the other.

**And the shard cost.** T01, T02, T03, T04 and T05 each add a test file,
so **five** files need measured costs, and the measurement must come from a
runner. The sequence is the one the project already established: the files
are put in the partition with apportioned costs, a run executes them, and the
measurement after that replaces the apportioned numbers. **No locally
measured number goes into the table** — and on this corpus the difference
was sixty-five times.

## 7. What "done" means

1. The migration and the ORM agree, and a row the schema must refuse is
   refused.
2. The fourteen acceptance clauses above have a named test each.
3. The demonstration runs, and **a test runs it**.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-08-acceptance.md` names the commit
   every number was measured at.
6. **An independent review at a named commit** — which, per the owner's
   decision of 2026-10-29, is the owner: they wrote none of this code, so
   they are the non-implementing reviewer the project's merge rule asks for.
