# Phase 2 — what a reviewer should attack

**Purpose.** The project's review moved after the merge (see
[`docs/handoff/CURRENT.md` § Merge authority](../handoff/CURRENT.md)), so
this file records **what should be broken, how to break it, and what should
catch the break** — written while the work was being done, by the agent that
did it, because an agent reviewing its own work afterwards would be
reviewing it from memory.

**How to use it.** Each row names a **claim** — something this work says is
true — the **file** that says it, the **mutation** that would make it
false, and the **witness** that should go red. A mutation is a change to the
*implementation*; a witness is a test that fails only because the property
broke.

**The rules for a mutation here, learned the hard way** (see §4):

1. **Apply it.** A mutation whose text does not match the formatted source
   changes nothing, and a green suite then means nothing.
2. **Make an assertion fail.** Deleting an assertion leaves the exit code
   at zero — a missing assertion is invisible to an exit code. Inverting a
   condition is what catches.
3. **Check the witness can see that kind of mutation** before reporting it
   as surviving.

---

## 1. The claims that carry the most weight

### 1.1 A similarity score never decides a version's order

**The claim.** ADR-0014 and the design both say it: *"禁止仅靠相似度静默确定
版本顺序"*. The alignment proposes; a person disposes.

| | |
|---|---|
| **File** | `src/labcairn/papers/alignment.py` — `propose_alignment` |
| **Mutation** | `ambiguous = margin < 0.05 and len(scored) > 1` → `ambiguous = False` |
| **Witness** | `test_the_alignment_refuses_when_the_evidence_points_two_ways` |
| **Also break** | `is_accepted` returns `self.accepted_by is not None or self.confidence >= 0.9` — decides acceptance by score |
| | `test_a_confident_proposal_is_still_unaccepted` |

### 1.2 A proposal may not wear a person's name

**The claim.** The schema's constraint asks *"does an acceptance name
somebody?"*; it does **not** ask *"is this edge an acceptance at all?"*. So
a row with `source='evidence'` and `accepted_by` set satisfies the schema
perfectly, and **the model** is what refuses it.

| | |
|---|---|
| **File** | `src/labcairn/papers/versions.py` — `_the_three_facts_stay_apart` |
| **Mutation** | delete the `accepted_by is not None and self.source is not EdgeSource.HUMAN` branch |
| **Witness** | `test_a_proposal_wearing_a_persons_name_is_refused`, `test_a_model_proposal_is_not_an_acceptance` |

### 1.3 A missing author stays missing

**The claim.** A revision with no `w:author` has an **unknown** author, not
an empty one and not a guessed one.

| | |
|---|---|
| **File** | `src/labcairn/material/ooxml.py` — the revision's `author` field |
| **Mutation** | `element.get(f"{{{W}}}author")` → `element.get(f"{{{W}}}author") or "unknown"` |
| **Witness** | `test_a_missing_author_or_date_is_unknown_and_never_guessed` |

**And the same rule for the date**: `test_every_revision_carries_its_kind_text_author_and_date`.

### 1.4 The deleted text is recovered

**The claim.** The deleted text lives in `w:delText`, and a reader that
reads `w:t` sees an empty run. **This is the property the whole phase
rests on.**

| | |
|---|---|
| **File** | `src/labcairn/material/ooxml.py` — `_text_in` |
| **Mutation** | the `w:delText` branch becomes `pass` |
| **Witness** | `test_every_deletion_text_is_recovered`, `test_every_revision_carries_its_kind_text_author_and_date`, `test_the_two_views_are_the_texts_adr_0014_names`, `test_a_revision_nested_inside_another_is_reported_separately` |

### 1.5 A comment with an unusable anchor is still a comment

**The claim.** The upstream study found a library that loses the whole
comment set when the range and element counts differ. Here, every comment
survives and the anchor is reported as unknown **with a reason**.

| | |
|---|---|
| **File** | `src/labcairn/material/ooxml.py` — `_collect_comments` |
| **Mutation** | `if anchor.status == "unknown": continue` — drop the comment |
| **Witness** | `test_every_comment_is_reported_including_the_unanchorable_ones`, `test_a_comment_with_no_resolvable_anchor_is_still_a_comment`, `test_each_unresolvable_anchor_names_its_own_reason` |

### 1.6 The view is part of the address

**The claim.** The same character range means different characters in the
accepted and the rejected text, so an address that did not say which view it
was in would be ambiguous — and the deleted text would have no address at
all.

| | |
|---|---|
| **File** | `src/labcairn/sources/locators.py` — `DocxLocator`; `src/labcairn/material/addressing.py` — `_docx_fields` |
| **Mutation** | drop `view` from the rendered key — the two views of one element collide on one row |
| **Witness** | `test_the_same_element_in_the_two_views_is_two_addresses` |

**And the direction that fails silently** — the *reconstruction* from the
key, where a dropped view resolves a citation against the other text and
nothing raises:

| | |
|---|---|
| **File** | `src/labcairn/evidence/index.py` — `locator_from_key` |
| **Mutation** | `view=fields["v"]` → `view="accepted"` |
| **Witness** | `test_a_docx_locator_is_rebuilt_from_its_key` |

### 1.7 A correction never overwrites

**The claim.** The edge the system proposed is **evidence about what the
system got wrong**. Overwriting it would destroy the record of the error.

| | |
|---|---|
| **File** | `src/labcairn/papers/versions.py` — `confirm_edge` |
| **Mutation** | `superseded = edge.model_copy(update={"superseded_by": corrected.edge_id})` → `superseded = edge` |
| **Witness** | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` |

**And the refusal is kept too**: a rejection that discards the proposal
it refused loses the fact that somebody already looked.

| | |
|---|---|
| **Mutation** | `corrects=edge` → `corrects=None` in the rejection branch |
| **Witness** | `test_a_rejection_writes_no_edge_and_keeps_the_proposal`, `test_the_three_outcomes_produce_three_different_shapes` |

### 1.8 A version is not its own parent, and the graph branches

**The claim.** The process branches — a student sent two different revised
drafts — so there is **no parent column on the version**.

| | |
|---|---|
| **File** | `migrations/versions/0010_paper_version_graph.py`; `src/labcairn/db/models.py` |
| **Mutation** | drop the `version_edges_not_self_parent` constraint |
| **Witness** | `test_a_version_cannot_be_its_own_parent` |

**And the other direction**, where the constraint is too **tight** — a
schema that required an acceptor for every edge would be unable to record a
proposal at all:

| | |
|---|---|
| **Mutation** | `(accepted_by IS NULL AND accepted_at IS NULL) OR (...)` → `accepted_by IS NOT NULL AND ...` |
| **Witness** | `test_a_proposal_with_no_acceptor_is_storable`, `test_a_high_confidence_proposal_is_still_unaccepted`, `test_a_branch_is_representable` |

### 1.9 The same bytes are one version; the same name is two

**The claim.** Two halves of one question with **opposite** answers.

| | |
|---|---|
| **File** | `src/labcairn/papers/duplicates.py` — `check_duplicates` |
| **Mutation** | `if len(labels) > 1:` → `if False:` — the hash decides nothing |
| **Witness** | `test_the_same_bytes_are_one_version_whatever_the_name` |

**And the gap is reported, not renumbered away** — a renumbering would
destroy the very gap it was reporting.

| | |
|---|---|
| **Mutation** | `missing = tuple(...)` → `missing = ()` |
| **Witness** | `test_a_missing_round_is_reported_and_nothing_is_invented`, `test_the_duplicate_and_gap_checks_are_independent` |

### 1.10 An edge may not cross projects

**The claim.** A CHECK constraint sees one row; this is a fact about three.

| | |
|---|---|
| **File** | `src/labcairn/papers/versions.py` — `check_edge_within_project` |
| **Mutation** | `if version.project_id != edge.project_id:` → `if False:` |
| **Witness** | `test_an_edge_to_a_version_outside_the_project_is_refused` |

---

## 2. The claims about the phase's framing

These are not code properties but statements the records make, and a
reviewer should check that the code agrees with them.

| The claim | Where to check |
|---|---|
| "the reader never writes" | `src/labcairn/material/ooxml.py` — there is no write path; the guard is `test_the_reader_module_writes_nothing` |
| "a file name and an mtime are never evidence" | `src/labcairn/papers/alignment.py` — the fingerprint has **no field** for either, and `test_a_file_name_never_decides_the_order` / `test_a_modification_time_never_decides_the_order` assert their absence |
| "the deleted text moved" | the number signal reports **both** sides of a moved number, because a span holding only the child's number says a number appeared rather than that a result moved — `test_two_drafts_that_differ_only_in_their_results_are_two_versions` |
| "an unresolved version is listed" | `paper_versions.status` defaults to `unresolved`, and the row is storable — `test_a_version_with_no_established_parent_is_unresolved_and_listed` |
| "the upstream repositories were read, not used" | `docs/research/upstream-study/` — no code copied; **three of the six ship no licence file at all** |
| "the shard costs came from a runner" | `.github/ci-shards.json` — `measured_at` names the commit the runner measured |

---

## 3. What the measurements say, and how to re-measure them

| The number | Where it is measured | How to re-measure |
|---|---|---|
| revision recall 30/30, deletion recovery 8/8, comment recall 14/14 | `docs/acceptance/LC-P2-07-fidelity-baseline.md` §5 | `python -m tests.evaluation_docx_fidelity --corpus-dir=<dir>` |
| the whole suite: 3894 passed, 0 failed | `docs/acceptance/LC-P2-08-acceptance.md` §5 | `python -m pytest tests/ -q --basetemp=<outside the repo>` |
| the shard costs | `.github/ci-shards.json` | `python .github/remeasure_shards.py <run-id>` |

**And the one measurement that found a defect**, worth a reviewer's attention
because it is the kind that a local run cannot see: the apportioned cost of
`test_paper_version_graph.py` was **0.64 s** and the measured cost was
**38.06 s** — sixty times out, because the fixture migrated the schema
twelve times. It is now **1.52 s**.

---

## 4. What the agent that wrote this got wrong

**Stated plainly, because a reviewer's time is better spent on the places
where the author knows the ground is soft.**

1. **Two mutations were reported as surviving that were not mutations.** One
   was never applied — its text did not match the formatted source — and one
   deleted an assertion instead of making it fail. The rule that follows:
   *a mutation must make an assertion fail*, and a survivor must be checked
   for having been applied at all.
2. **The guard-count witness is weak, and its docstring says so.** It catches
   a bulk removal of a demonstration's guards and **not** a single one,
   because a count with a floor is not an identity. A reviewer wanting a
   stronger guard would have to give every guard a name and assert the
   *set*.
3. **The alignment's 0.05 margin is a guess.** It is documented as such, but
   a reviewer may reasonably ask whether the near-tie threshold should be
   derived from the corpus rather than chosen.
4. **The round-detection patterns are English- and Chinese-shaped by
   hand.** `v2`, `version 2`, `第2稿` are covered; `rev3-final`, `Draft_02`
   and `第三次修改` are not. A reviewer with a real file name in mind may
   find a miss.
5. **The reader has never seen a real Word document.** The corpus is
   synthetic, and the ten cases in its `KNOWN_GAPS` are the pilot's job.
   The most likely real-world failure is **run fragmentation inside a
   revision**, which the corpus cannot produce.
6. **The `view` field assumes two views.** A document with a tracked
   *formatting-only* revision, or one whose revisions interact with
   numbering, may not decompose cleanly into the two the design names.

---

## 5. Where the next work starts

**LC-P2-06, the data governance**, and the claims it has to earn are in
[`docs/adr/ADR-0015-dataset-consent-and-access.md`](../adr/ADR-0015-dataset-consent-and-access.md).
Its acceptance clauses are already written; what is not yet written is the
task breakdown, and that is the next thing in the queue.
