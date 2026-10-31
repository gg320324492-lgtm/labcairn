# LC-P2-08 — The paper project and the version graph: acceptance

**Work order:** LC-P2-08 (the paper project, the version graph, and the
alignment) · **Subtasks:** T00–T05.
**Task breakdown:** [`docs/plans/LC-P2-08-task-breakdown.md`](../plans/LC-P2-08-task-breakdown.md)
**Status of the work order:** **implemented and measured**, and **not
independently reviewed** — see §7.
**Measured:** 2026-10-29 on the tree at `4aff29b`, on Windows 11 (AMD64),
Python 3.12.13. **§6 was added 2026-11-01**: the revision events, their
writer, their reads, their witnesses and their measurement over real
material — see §6.5 for the machine and the date, and §6.6 for the two
limits that record carries.

**What this is.** The first implementation of the mentor-trajectory line:
the tables a manuscript's versions live in, the contracts that hold them, the
alignment that proposes which version came from which, the human path that
settles it, the two checks that are about not lying about an archive, and —
since 2026-11-01 — **the table ADR-0014 declared and nothing ever wrote**:
one row per tracked change a manuscript's file records.

**What this is not.** It is not the guidance agent, and it is not the
experience store. The reader that produces the events these tables will
hold is LC-P2-07's, and it is measured
([`LC-P2-07-fidelity-baseline.md`](LC-P2-07-fidelity-baseline.md)); the
feedback chain is LC-P2-09's. **What this work order stores is where a
version came from; what LC-P2-09 stores is what happened inside one.**

---

## 1. The three decisions, and where each is held

| The decision | Held by | Witnessed by |
|---|---|---|
| **A version graph, never a version list** — the process branches, and a column holding one parent cannot hold two | the schema: `paper_versions` has **no parent column**, and the parent lives in `version_edges` | `test_a_branch_is_representable` |
| **The edge carries how it was decided; the confidence is not the decision** | the schema's `version_edges_acceptance_names_an_acceptor` and the model's validator | `test_a_confident_proposal_is_still_unaccepted`, `test_an_edge_with_no_acceptor_is_refused`, `test_a_proposal_wearing_a_persons_name_is_refused` |
| **An unresolved relationship is a value, not an absence** | the schema's `status` column and the model's default | `test_a_version_with_no_established_parent_is_unresolved_and_listed` |

**And the fourth, which the schema cannot hold:** an edge's two versions
must belong to the edge's project. A CHECK constraint sees one row; this is
a fact about three, so the **model** says it —
`check_edge_within_project`, witnessed by
`test_an_edge_to_a_version_outside_the_project_is_refused`.

## 2. The fourteen acceptance clauses

Every clause in the task breakdown's §4 names a test, and the test exists.

| # | The clause | The test |
|---|---|---|
| A1 | Two files with the same name and different bytes are two versions | `test_two_files_with_the_same_name_and_different_bytes_are_two_versions` |
| A2 | Two files with the same name and the same bytes are one version | `test_the_same_bytes_are_one_version_whatever_the_name` |
| A3 | A version with no established parent is `unresolved` and is listed | `test_a_version_with_no_established_parent_is_unresolved_and_listed` |
| A4 | The order is never taken from a file name | `test_a_file_name_never_decides_the_order` |
| A5 | The order is never taken from an mtime | `test_a_modification_time_never_decides_the_order` |
| A6 | A proposal with high confidence is still unaccepted | `test_a_confident_proposal_is_still_unaccepted` |
| A7 | An edge claiming a human decision with no acceptor is refused | `test_an_edge_with_no_acceptor_is_refused` |
| A8 | An edge with `source='evidence'` and an `accepted_by` is refused | `test_a_proposal_wearing_a_persons_name_is_refused` |
| A9 | The alignment refuses to decide when the evidence points two ways | `test_the_alignment_refuses_when_the_evidence_points_two_ways` |
| A10 | Two drafts whose prose matches and whose numbers differ are two versions | `test_two_drafts_that_differ_only_in_their_results_are_two_versions` |
| A11 | A missing round is reported, and no version is invented | `test_a_missing_round_is_reported_and_nothing_is_invented` |
| A12 | A correction is a new version of the edge, and the old one stays readable | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` |
| A13 | An edge whose parent is outside the project is refused | `test_an_edge_to_a_version_outside_the_project_is_refused` |
| A14 | The demo is run by a test | `test_the_paper_version_demo_runs` |

**Two of the fourteen had no witness when this record was written**, and
both are now implemented: **A13** was a real gap (the schema cannot hold it
and the model did not either), and **A3** had the property but not under
the name the breakdown gave it. **The breakdown is the contract, so the
tests were renamed to the breakdown's wording** — the eleven whose names had
drifted — rather than the other way round.

## 3. The mutations, and what each broke

**A witness that has never been broken is not known to be a witness.**

| # | The mutation | What went red |
|---|---|---|
| 1 | the self-parent constraint is dropped from the migration | `test_a_version_cannot_be_its_own_parent` |
| 2 | the acceptance-names-an-acceptor constraint is dropped | `test_an_edge_that_claims_an_acceptance_must_name_the_acceptor` |
| 3 | **the acceptance constraint is reversed**, so every edge must name an acceptor | `test_a_proposal_with_no_acceptor_is_storable`, `test_a_high_confidence_proposal_is_still_unaccepted`, `test_a_branch_is_representable` |
| 4 | the proposal-may-not-name-an-acceptor refusal is dropped from the model | `test_a_proposal_wearing_a_persons_name_is_refused`, `test_a_model_proposal_is_not_an_acceptance` |
| 5 | acceptance is decided by the **confidence** rather than by who accepted | `test_a_confident_proposal_is_still_unaccepted` |
| 6 | the alignment's ambiguity margin is removed, so a near-tie always decides | `test_the_alignment_refuses_when_the_evidence_points_two_ways` |
| 7 | the fingerprint collects **no numbers** | `test_two_drafts_that_differ_only_in_their_results_are_two_versions`, `test_the_number_signal_is_not_optional`, `test_a_version_with_a_changed_result_is_not_the_same_version` |
| 8 | the correction **overwrites** the proposal instead of superseding it | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` |
| 9 | the proposal a **rejection** was about is discarded | `test_a_rejection_writes_no_edge_and_keeps_the_proposal`, `test_the_three_outcomes_produce_three_different_shapes` |
| 10 | the content hash decides nothing about duplicates | `test_the_same_bytes_are_one_version_whatever_the_name` |
| 11 | the gap is **renumbered away** | `test_a_missing_round_is_reported_and_nothing_is_invented`, `test_the_duplicate_and_gap_checks_are_independent` |
| 12 | a cross-project edge is allowed | `test_an_edge_to_a_version_outside_the_project_is_refused` |

**Mutation 3 is the one worth reading twice.** A constraint that is too
loose admits a fake acceptance; one that is too tight kills the proposals
the system exists to produce. **Both have witnesses**, and they are on
opposite sides of the same rule.

### 3.1 What a mutation cannot be, and what was learned the hard way

**Two mutations "survived" in this work order, and neither was a mutation.**

1. **One was never applied.** The text to be mutated did not match the
   formatted source, so the file was unchanged and the suite was green.
   **A mutation that was never applied is reported as a surviving
   mutation by anyone who does not check.**
2. **One deleted an assertion instead of making it fail.** Replacing a
   demonstration's guard with a comment leaves the demonstration running,
   printing its steps, and exiting zero: **a missing assertion is
   invisible to an exit code.** The effective mutation is the one that
   **inverts a condition**, and it is caught by five tests at once.

**The rule, and it is in the test file's docstring so the next reviewer
does not have to rediscover it:** *before reporting a surviving mutation,
check that the mutation **applied**, that it changed an **assertion's
condition**, and that the witness could **see** that kind of mutation.* A
guard-count witness catches a bulk removal and not a single one, because a
count with a floor is not an identity — and the limit is stated rather than
papered over.

## 4. What was measured

| | |
|---|---|
| **The whole suite** | see §5 |
| **The corpus and the reader** | revision recall 30/30, deletion recovery 8/8, comment recall 14/14 — [`LC-P2-07-fidelity-baseline.md`](LC-P2-07-fidelity-baseline.md) |
| **The schema** | the migration and the ORM agree — `tests/test_evidence_schema.py`'s parity test walks `Base.metadata` and the migrated schema independently |
| **The refusals** | every rule above is witnessed by **writing a row the schema must refuse**, not by comparing two texts. The project's own lesson from revision 0007 is that a parity test cannot catch both the migration and the ORM being wrong together |

## 5. The suite on this tree

**Measured on `4aff29b`** — the commit the runner measured, and the tree
this record was written at.

```
3894 passed, 5 skipped, 0 failed, in 34 minutes 56 seconds
```

**The five skips are all of the project's own accepted kinds**: a
POSIX-only permission-bit case, the real-provider smoke that needs the
owner's credential, and three Windows-path cases. **None of them is new**,
and none of them is about this work order.

**And the CI run on the same tree is green**: 17 checks, both platforms,
all five shards each.

### 5.1 The shard cost, and the sixty-fold error it caught

**The two-step process found a real defect, and this is why it exists.**

| | The apportioned cost | The measured cost |
|---|---|---|
| `test_paper_version_graph.py` on Windows | 0.64 s | **38.06 s** |

The apportioned number is what the shard table carried before the file was
ever executed, and it was **sixty times too small**. The cause was the
fixture: the migration ran in a **function-scoped** fixture, so the whole
schema was built twelve times, once per test, and the measured durations
showed every test's *setup* at about a third of a second.

**Fixed** — the migration runs once for the module and each test gets a
**copy** of the migrated file (a copy matters: several of these tests have
their writes *refused*, and a refused write leaves a transaction the next
test must not inherit). The file went from 3.9 s to 0.4 s here, and from
**38.06 s to 1.52 s** on the Windows runner.

**A file placed on a sixty-fold error would have been put in the wrong
shard**, and the partition is balanced on the measured numbers. The rule
that the costs come from a runner is not ceremony: **the runner is the only
place that can tell "this file is slow" from "this file migrates the
schema twelve times."**

`measured_at` is `4aff29b`, and both platforms balance at 1.000.

## 6. The seam closed: ADR-0014's revision events (2026-11-01)

**What the debt was**, in the work order's own words: *"LC-P2-07's reader
produces the revision events these tables are meant to hold, and nobody has
written them into the store yet: the reader exists, the store exists, and
the seam between them is not wired — so the version graph is presently fed
by hand."*

**What is in the tree now.** The table `revision_events` (migration
`0017_revision_events.py`), the writer
`src/labcairn/papers/revisions.py::record_revision_events`, and the reads
`src/labcairn/application/chain.py::read_revision_events` and
`::read_revision_activity`.

### 6.1 Why it is a table of its own, and not the chain's `edit_actions`

**ADR-0014 D8 declared four tables** — `PaperVersion`, `VersionEdge`,
`DocumentSpan` and `RevisionEvent` — **and only the first two were ever
written.** The reader has produced the third since LC-P2-07 and nothing in
`src/` stored it, so a marked-up manuscript was a file the archive could
cite and could not describe.

**And the chain's tables are the wrong place for it.** They are a
*judgement* layer: a comment, a change made in answer to it, the judgement
that it answered, a later assessment. `edit_actions` is content-free **by
design** — it names an edge and an actor, and the content belongs to the
document model, which is ADR-0014's. Putting a revision's text into
`edit_actions` would have put a document-level observation into a
judgement table, and it would have needed a SQLite table rebuild (revision
0002's lesson: batch mode stamped the revision as applied and changed
nothing).

**And the chain's `feedback_events` could not have held it either.** Its
locator is into `word/comments.xml` *by definition* and its docstring says
*"The advisor's words."* **On the corpus that motivated this table, no
file carries a comments part at all** — so the chain's comment table writes
zero rows on that material, and putting revisions there would have been a
green tree saying something false.

### 6.2 The table, and the clause each column answers

| Column | Null | The clause it answers |
|---|---|---|
| `revision_event_id` | no, PK | caller-minted, and **derived** from the version and the element's path, so recording the same file twice is the same rows |
| `version_id` | no, FK `paper_versions` | which manuscript version's document the event was read from. The version carries the file **and** the bytes, so the event repeats neither |
| `kind` | no | `ins` / `del` / `moveFrom` / `moveTo` — the reader's four, and a closed vocabulary |
| `text` | no | the inserted or the deleted text. **Empty is a real value**: Word records an empty tracked insertion, and 71 of the 897 events in the corpus below carry empty text |
| `text_sha256` | no | **D5** — the hash of that text at the moment it was recorded; a mismatch is a stale anchor |
| `part` | yes | **D5** — the package part the element is in |
| `element_path` | yes | **D5** — the path of the `w:ins` / `w:del` element |
| `view` | yes | **D4a** — `accepted` or `rejected`; the view is part of the address, so a deletion is addressed in the rejected view |
| `char_start`, `char_end` | yes, paired | **D5** — the range inside the addressed element's text in that view |
| `paragraph` | yes | the paragraph the event sits in |
| `baseline_start`, `baseline_end` | yes, paired | the range in the paragraph's **rejected** text — the coordinate system that makes a deletion addressable at all |
| `author` | yes | **D3** — the revision's author, or `None` when the file records none. An *empty* author is not a missing one, and the two are kept apart |
| `author_unknown_reason` | yes | **D3** — why the author is unknown, and present exactly when the author is not |
| `occurred_at` | yes | **D3** — the revision's timestamp, or `None` |
| `date_unknown_reason` | yes | **D3** — why the timestamp is unknown |
| `element_id` | yes | Word's `w:id`; it pairs a move's source with its destination |
| `nested` | no | a revision inside another revision is reported separately, so the flattening is **detectable** |
| `parser_version` | no | **D5** — derived from the reader's own source, so changing the reader changes the version without anybody remembering to bump a constant |
| `grade` | no | **D2** — `observed` / `inferred` / `human_verified` |
| `created_at` | no | when the event was recorded |

**And the grade governs the address.** An `inferred` row read no file, so
it quotes nobody and points at nothing: the schema refuses an `inferred`
row that carries words, and refuses a read row that carries no address.
That is the rule `feedback_events` already holds for the comment's
locator, stated here for the same reason — *a row carrying an address
nobody read is the file being claimed to have said something.*

### 6.3 The operations, and what they refuse

| Operation | What it does | What it refuses |
|---|---|---|
| `record_revision_events(context, project_id=, version_id=, now=)` | reads the version's material, asks the policy about it, checks the bytes against the version's own hash, parses the document, and writes one row per tracked change | the project or the version is not there; the version belongs to another project; the material is missing, unreadable or drifted; the policy denied it; an anchor is stale |
| `list_revision_events(context, version_ids=)` | the events the store holds, **denied material dropped rather than refused** (ADR-0003 C5) | — |
| `read_revision_events(context, version_ids=)` | the changes, with their words and their addresses | — |
| `read_revision_activity(context, version_ids=)` | per version: the number of changes, the number of paragraphs they fall in, the largest number in one paragraph, and the number of comments the chain holds for the same version | — |

**The bytes are checked before anything is written.** The version names the
file *and* the bytes it was recorded with, and the file on disk is compared
against those bytes before it is parsed. A manuscript that has changed
under the name is not the one the coordinates would name, so **nothing** is
recorded against it — not a wrong event, and not a silent re-point.

**And the ids are derived.** An event is cited from a later run and from a
decision record, so its identity cannot depend on insertion order; the id
is a function of the version and the element's path.

### 6.4 The witnesses, and the mutations that broke them

**Twelve witnesses** — eleven functions and one with twelve parameterised
cases, so twenty-three cases — all in `tests/test_version_store.py`, the
file that is about *storing* the paper project's rows, plus one more in
`tests/test_threat_model.py`. **Not a new file:** a new `tests/test_*.py`
has no measured shard cost, and `tests/test_ci_shard_coverage.py` fails on
a file with no cost until a runner measures it.

| The property | The witness |
|---|---|
| the change's words and its address travel together, and the file agrees with the row | `test_a_revision_event_carries_the_text_and_the_place_of_the_change` |
| a deletion keeps its text, and is addressed in the rejected view | `test_a_deletion_keeps_its_text_and_is_addressed_in_the_rejected_view` |
| a missing author or date is unknown, and the absence is named | `test_a_revision_with_no_author_or_date_is_unknown_and_never_guessed` |
| each of the schema's eleven rules refuses the row that breaks it | `test_the_schema_refuses_a_revision_event_that_breaks_its_rule` (twelve cases) |
| recording the same version twice is the same rows | `test_recording_the_same_version_twice_is_the_same_rows` |
| a row whose text no longer matches the file is refused as stale, not re-pointed | `test_a_revision_whose_text_no_longer_matches_is_refused_as_stale` |
| a manuscript whose bytes changed under its name is refused | `test_a_manuscript_whose_bytes_changed_under_its_name_is_refused` |
| a denial of the material writes nothing | `test_a_revision_event_is_not_recorded_when_the_policy_denies_the_material` |
| a version nobody holds is refused | `test_a_revision_event_about_a_version_nobody_holds_is_refused` |
| a listing drops the events of denied material rather than refusing | `test_a_listing_drops_the_events_of_denied_material` |
| the mentor line reads the changes and the shape of the manuscript | `test_the_application_layer_reads_the_revision_events_and_the_activity` |
| **the schema cannot express why a change was made** | `test_the_schema_cannot_express_why_a_change_was_made`, and `tests/test_threat_model.py::test_the_revision_events_cannot_carry_a_reason` |

**Twenty-three mutations were applied, and none survived.** Each broke one
property — a constraint removed from the table *and* from the migration, a
text dropped, a view dropped, an author guessed, an id that depends on
insertion order, a stale anchor re-pointed instead of refused, the byte
check skipped, the policy not asked, the refusal for the wrong reason, a
count that counts nothing, a listing that does not drop denied material,
and a column added for the reason a change was made. **Every one of them
was caught by the witness that claims that property, and each by its own.**

**And one of the twenty-three was not applied at first**, because a
reformat had moved the line the mutation named. **A mutation that was never
applied is reported as a surviving mutation by anyone who does not check**,
so the pass reports the two that did not apply as *not applied* and runs
them again — and the record says so rather than quietly reporting a
twenty-one.

### 6.5 What was measured over the real material

**The reader was measured against the package's own XML**, so it was
measured against something it did not produce. **Measured locally** on
Windows 11 (AMD64), `DESKTOP-BJJHSDF`, Python 3.12.10, at
2026-10-31T18:12:05Z (2026-11-01 local). **This is a local measurement
and not a runner's**, and the record says so.

| | |
|---|---|
| **revision recall on real files** | **897 / 897** — every tracked-change element in the five review copies, counted from `word/document.xml` |
| **deletion recovery** | **3 907 / 3 907** characters — the `w:delText` of the deletions and the text of the one `w:moveFrom` |
| **insertion recovery** | **7 048 / 7 048** characters |
| **comments** | **0** — and **no file in the corpus carries a `word/comments.xml` part at all** |
| **files carrying revisions** | 5 of 15; the six drafts, the clean English manuscript and the three reply letters carry none |

**And the property the old baseline cannot see.** LC-P2-07's baseline is a
recall measure on synthetic fixtures, and it cannot tell "300 events in 14
paragraphs" from "300 events in 300 paragraphs". **On real files the
distribution is the finding**:

| File | Changes | Paragraphs with a change | Paragraphs in the document | Busiest paragraph | Median per changed paragraph |
|---|---|---|---|---|---|
| `v08-05-chinese-review` | 203 | 43 | 113 (38.1 %) | 34 (16.7 % of the file) | 2 |
| `v08-16-chinese-review` | 225 | 25 | 106 (23.6 %) | 53 (23.6 %) | 3 |
| `v09-04-chinese-review` | 303 | **14** | 113 (**12.4 %**) | 77 (25.4 %) | 13 |
| `v09-07-chinese-review` | 52 | 6 | 90 (6.7 %) | 31 (**59.6 %**) | 3 |
| `v09-25-chinese-review` | 114 | 11 | 111 (9.9 %) | 39 (34.2 %) | 6 |

**Three real cases the synthetic corpus does not reach**, all three of them
in the material rather than in a fixture: **71 events carry empty text**
(a tracked insertion of nothing is a thing Word writes), **one document
holds a revision inside another revision** (`docx_nested_revision`), and
**one `w:moveFrom` carries its text in `w:t` rather than in `w:delText`**.

**And the measurement caught the measurement.** The first version of the
counter read only `w:delText` and under-counted the corpus by 83
characters; the reader's number was the right one and the counter's was
wrong. **A record is not evidence, and where they differ the measurement
wins** — so the counter was corrected and the number above is the
corrected one.

### 6.6 The two limits, stated here rather than only in a report

1. **The revision events are not on the event stream, and so they cannot be
   replayed from it.** ADR-0017 D8 puts the chain's four objects on the
   append-only stream, and this is a **fifth** object without a fifth
   event. Adding one means an enum member, a payload model, an emit
   function and the chain events' witness table — in `runtime/`, which this
   work did not touch. **The claim is not made and the gap is not hidden.**
2. **The fidelity measurement is local.** It is a measurement of the reader
   against real files, run on one machine, and the record names the machine
   and the date. **No shard cost comes from it**, and nothing in it is
   presented as a runner's number.

### 6.7 What was deliberately **not** built, and why

- **`document_spans`, ADR-0014's other unbuilt table.** D5's flat form is
  the floor the ADR's chosen alternative already meets, and a span table
  earns its place when two things must **share** one address. Nothing
  does yet — and the thing that will is the author's reply letter, which
  points at a *passage* in the manuscript rather than at a change, and
  which belongs to the peer-review loop's own work order. **It is the next
  piece, not this one.**
- **The reply letter's exchanges.** They are not a chain link:
  `response_links` requires an `edit_action_id`, and the passage an answer
  is about is not a change. They are also, in the material as extracted,
  an unsigned extraction — and the project's own precedent is that an
  extraction which does not name who produced it cannot be imported as an
  observation.
- **Anything that turns a reviewer's rewrites into a rule.** **ADR-0016 D9
  calls the agreement between a system and an advisor's wording a *risk
  metric* rather than a quality metric**, and 897 silent rewrites are
  exactly the material that would be mistaken for the advisor's rules.
  **The schema is what stops it:** `revision_events` has no column for a
  reason and no foreign key to `feedback_events`, and the rule store's
  only binding to chain material is by `issue_key`, which a revision event
  does not carry. **"Distil a rule from the reviewer's rewrites" is not
  expressible in the data model at all** — which is §6.13 of the threat
  model and its witness.
- **The group's own writing template.** It is a *rule* object, it has no
  `issue_key`, and it cannot be a rule's source under the current schema
  (`guidance_rule_sources.issue_key` is NOT NULL). What it needs is a
  **"rule → the check that can decide it"** binding, which does not exist
  in the tree, and its pre-submission checklist is a catalogue of decidable
  checks rather than a rule or a counterexample. **That is LC-P2-11's
  decision and not this work order's**, and it is handed over as such.

## 7. What this work order has not had

- **No independent review.** The project's rule is that a work order is
  accepted on an **independent review at a named commit**, and per the
  owner's decision of 2026-10-29 the reviewer is the owner — they wrote
  none of this code. **That review has not happened yet**, and this
  document does not claim it has.
- **No real material.** Everything here is synthetic. A real manuscript
  brings run fragmentation inside a revision, revision ids Word renumbers on
  save, comments in headers and footnotes, and adviser prose with hedging
  and politeness in it. **The reader has never seen one**, and the
  pilot corpus is where it will.
- ~~**No persistence of the events.** The tables hold projects, versions and
  the edges between them. **LC-P2-07's revision events are read and then
  go nowhere**, because the tables they would live in — `EditAction`,
  `FeedbackEvent`, `ResponseLink` — are LC-P2-09's.~~ — **closed
  2026-11-01 by §6.** The events were not going into LC-P2-09's tables at
  all: ADR-0014 D8 declares a table of their own, and they now have one —
  `revision_events`, with its writer, its reads and its witnesses. **What
  is still missing is the fifth event type**: the revision events are not
  on the append-only stream, so they cannot be replayed from it (§6.6).
- **No clustering into projects.** Which material belongs to which paper is
  the harder question, and it is a question about *identity* rather than
  about *history*. A version's parent is decidable by evidence; a version's
  project is declarable by a person.
- **No intake.** The design's §7 names the zip bomb, the path traversal
  and the macro. **None of those is a version-graph question**, and they
  belong to LC-P2-06's, because intake is where a grant is checked.
- **No retrieval over the graph.** LC-P2-11's case retrieval needs an
  index, and the index needs LC-P2-05's widened corpus to be measured
  against.

## 8. The next thing

**LC-P2-06, the data governance.** Its grant table names the paper project
this work order created, so the two fit together — and the reader's events
have nowhere to live until the response tables do.

**And one thing that is not a ticket:** the CI shard cost for this work
order's four new test files. The rule is that the cost must come from a
**runner**, and the two-step process for that is recorded in the Phase 2
evidence pack — the first run apportions, the second measures.

**And one more, from §6:** the revision events are **not on the event
stream**, so they cannot be replayed from it. ADR-0017 D8 puts the chain's
four objects there; this is a fifth object waiting for a fifth event, and
the event type is a change to `runtime/` that this work order did not
make.
