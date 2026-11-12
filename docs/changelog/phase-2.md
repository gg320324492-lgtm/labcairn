# Changelog archive — Phase 2 — closed, never released

Archived verbatim from the root [`CHANGELOG.md`](../../CHANGELOG.md) on
2026-11-11. The body is byte-identical to the sections as they stood there,
except that each relative link gained the depth of `docs/changelog/`.
The root file keeps [`[Unreleased]`](../../CHANGELOG.md#unreleased) as the
container and [the archives index](../../CHANGELOG.md#archives).

### Phase 2 final closeout (2026-11-06)

- PR #148 merged as `0d654b2038051805eb0ab410783ea2fe90545506`; its delivery
  branch was deleted locally and on the remote.
- Batch 11's two-paper version graph, approved real-store write and three
  negative witnesses landed locally; both scratch refs were deleted.
- The owner confirmed the holder and authority to grant MIT. The root
  `LICENSE` carries `Copyright (c) 2026 Tonghe Du`;
  `LICENSE.PENDING.md` was deleted, and the current-state documents,
  release metadata and licensing witnesses were updated together.
- Phase 2 administrative closeout is CLOSED; the final open items are in
  [`LC-P2-28-phase2-open-items.md`](../acceptance/LC-P2-28-phase2-open-items.md).
  Phase 3 has not started.
- The owner authorised a Phase 3 scoping / ADR pack only. It records
  boundaries, dependencies and owner decisions; it creates no work order and
  starts no Phase 3 implementation.
- The owner's follow-up decisions archive `ADR-0020` and `LC-P2-28` as
  historical Phase 2 design, defer every candidate Phase 3 scope family, and
  leave the real-provider smoke NOT RUN with no credential configured. The
  local record commits were initially held locally.
- An operator-side WSL measurement of the POSIX-only path and session-directory
  witnesses is recorded outside the repository. It does not change the frozen
  Phase 2 gate record.

### Repository tidy (2026-11-06)

- A read-only classification found 727 tracked files, 199 Python test files,
  3,419 declared test functions and no exact-byte duplicate groups. The
  [`REPOSITORY-MAP.md`](../REPOSITORY-MAP.md) records where each class
  lives; no witness, fixture or historical acceptance record was removed.
- Current-state pointers in the bilingual READMEs, documentation index,
  roadmap, handoff and `web/package.json` now agree with MIT and the CLOSED
  Phase 2 closeout. Dated gate snapshots keep their original wording.
- The GitHub repository description no longer says licensing is pending.
- The owner authorised one tidy delivery PR and one runner run to carry the
  local records online. This changelog claims no runner result before the
  pull request reports one.

### Phase 2 work, recorded by category

**Added**

- **The manuscript read ceiling is 96 MB, raised from 64 MB.** The third
  pilot's late drafts are 71.4 MB — full-resolution figures embedded — and
  the 64 MB ceiling refused **seven versions of one real manuscript**,
  including its final English version, at ingestion. The four ceilings
  (`feedback`, `replies`, `revisions`, and the read-only source port's
  default) carry the same number deliberately, and a file is still
  **measured before it is read**: the ceiling is a measurement, not a
  caller's claim.

- **Two acceptance records now name the witness the mutation actually
  reddens.** LC-P2-10's M22 row names
  `test_every_item_has_two_annotations_and_a_resolution` for the
  deleted-count form; the completion-check witness it used to name reddens
  only under the *mis*-counting form (`!= 1`), because this tree's manifest
  is finished and that witness takes its finished branch. LC-P2-16's
  mutation-8 row now says the fixed project must be one the store **holds**:
  a nonexistent id is refused by the same 403 as the absent caller id and
  leaves the witness green. Both forms were re-applied and measured before
  the records were corrected; both review files carry a resolved note.

- **Three support modules no longer wear the `test_*` glob.**
  `tests/test_store_support.py`, `tests/test_recovery_support.py` and
  `tests/test_skill_support.py` were shared fixture modules — 47 test files
  import them — that pytest collected and found no case in, and that the shard
  list carried on both platforms (**one shard each, never every shard: of the
  revisions of `ci-shards.json` that name them at all — 56 of the file's 84 — **55
  place them in a shard group and 54 place each in exactly one shard group on each of
  the two platforms**; the one that drops out of the second figure is the 2026-10-24
  single-platform table, and the named-but-never-placed one is the 2026-11-02 removal —
  no revision ever placed one in more than one shard. The
  "every shard" wording this entry and the Phase 1 board row printed was wrong from
  the day the finding was filed**). They are now `tests/store_support.py`,
  `tests/recovery_support.py` and `tests/skill_support.py`; their shard and
  cost entries and their evaluation-manifest rows are gone, and the
  collected-nothing mechanism keeps its witness through a synthetic
  selected-and-empty run. `python .github/make_ci_shards.py` re-balanced
  both partitions from the existing runner costs (Ubuntu 1.231, Windows
  1.000) without a CI run.

- **ADR-0006's outbound-consent bridge — a Phase 1 debt closed.** The
  provider layer can no longer send without a permission decision: an
  `OutboundConsent` port is a **required constructor argument**, and
  `send` calls it after the local pre-flights and **before the
  transport**, so an approval that is missing, pending, expired or
  already spent refuses the request with the wire never reached. The
  permission decision crosses the boundary **as a value, not as an
  import** — the two capability vocabularies stay disjoint (ADR-0006
  statement 1), and the approval's single use is spent only by a call
  that will actually be made. 8 witnesses; 5 self-reported mutations
  and 4 independent ones, all caught.
  [LC-P1-03 outbound bridge](../acceptance/LC-P1-03-outbound-bridge.md).

- **The blind evaluation's mechanical preparation (LC-P2-14).** Four
  pieces under `tests/evaluation/`: the protocol's five arms as data a
  configuration is measured against; a by-paper leak check that names
  every leak shape it knows (a paper on both sides, an entry with no
  side, an entry on the wrong side, a rule built on an evaluated paper,
  a side the checker does not know); an anonymous blind sheet that
  **refuses** a document carrying an arm key rather than cleaning it;
  and an exact paired sign test whose **not-significant verdict is a
  first-class outcome** — a small denominator is not significant by
  rule with no p-value computed, all-ties says "no evidence either
  way", and every significant row carries its denominator. 64
  witnesses; 47 mutations self-reported and all caught; 4 further
  mutations applied independently, all caught.
  [LC-P2-14 preparation](../acceptance/LC-P2-14-preparation.md).

- **Five acceptance records carry an independent review.** Every
  mutation in the reviewed records re-applied by a session that built
  none of them, every witness watched: LC-P2-02/07/09 hold;
  LC-P2-10/16 hold with notes. The reviews are records of the checking
  (`docs/acceptance/LC-P2-{02,07,09,10,16}-review.md`), not of new
  work.

- **The P1 baseline is frozen.** The phase's exit gate — *"measured
  capability gain against a frozen P1 baseline"* — had no denominator:
  the harness could read a baseline document and nothing supplied one.
  The baseline is now committed at
  [`docs/acceptance/LC-P2-00-baseline.json`](../acceptance/LC-P2-00-baseline.json),
  measured on `main` at `81babd5` (Windows 11, offline): five gate
  classes, four measured metrics, the real-provider smoke honestly
  recorded as NOT RUN, and `model: ""` rather than an invented name.
  **A run on the same tree compares on all six conditions**, a doctored
  run and a doctored baseline are each refused by name, and the record
  says what the numbers do not establish.
  [LC-P2-00 baseline](../acceptance/LC-P2-00-baseline.md).

- **The settlement over a reply — the peer-review loop's judgement
  half.** The reply was a record of what was said and nothing judged it;
  `reply_settlements` (migration `0020`) and `settle_reply` add the
  judgement. **A response whose claimed experiment the manuscript does
  not contain is refused or held, by name**; an unjudged reply stays on
  the unsettled listing; the change is placed in the manuscript or the
  settlement says it could not be; and a disagreement between the
  chain's judgement and a settlement is shown as **two sides**, not
  resolved by recency. A model may put a settlement forward and may not
  decide one.
  [LC-P2-09 acceptance](../acceptance/LC-P2-09-acceptance.md) §10.

- **The reader reports one tracked change once.** A paragraph whose run
  carries a drawing — Word's `mc:AlternateContent`, a `Choice` and a
  `Fallback` each wrapping a text box — had its inner revisions reported
  a second time by the outer paragraph's walk: **243 events where the
  file holds 239 addresses**. The walk now reports a revision only from
  the nearest containing paragraph, and **the corpus carries the shape**
  (fixture 30), so the corpus-wide witnesses catch the defect by
  construction. Verified on the real file both ways: 243 before, 239
  after; the pilot's chain was checked unpolluted.
  [LC-P2-07 fidelity baseline](../acceptance/LC-P2-07-fidelity-baseline.md).

- **The mentor's own material, in the product — and the chain's four
  rings.** The second corpus is a second paper with a second advisor, and
  the two of them are in the product as two pilot projects: **twenty
  versions, eighty comments (forty-six on the first paper, thirty-four on
  the second), 1528 recorded changes** and the owner's own
  judgements on ten of the correspondences the operator put forward.
  **The denominator of this row is not named here, and it should not be
  taken as a count of the two projects together:** 1528 is what
  [`../acceptance/LC-P2-09-acceptance.md`](../acceptance/LC-P2-09-acceptance.md)
  §9.1 measured on the pilot's own workspace on 2026-11-01, and
  [`../handoff/CURRENT.md`](../handoff/CURRENT.md) names it as the first
  paper's. The figure that stands in that same sentence in
  [`../plans/PHASE_2-work-orders.md`](../plans/PHASE_2-work-orders.md) and
  [`../ROADMAP.md`](../ROADMAP.md) today is **1819**, from a
  re-measurement on 2026-11-02 — a later date than this entry, and **a figure
  this archive row has never carried itself**: `grep -c 1819` on this file at
  `0655bb8b22506dd851e1eff6f29a455465535a1a` exits 1 with a count of 0 (it is
  3 here only because the note you are reading names the figure), and the
  1819 sentence itself lives only in the two plan and roadmap records.
  **Which corpus each covers is stated
  nowhere in the tree**; see the "Read the denominators together" paragraph of
  the work-order plan. **The
  chain's second ring holds one row per change a manuscript's file
  records** — `edit_actions`, 1439 of them, because the other 89 are the
  marks an operation at a point leaves behind and **the chain records
  changes and not marks** — and **the third ring holds the
  correspondences and their judgements**: the operation that puts a link
  forward **has no state to decide it with**, because the third ring is
  filled by a person or a rule. **The memory serves one rule of sixteen
  and reports the other fifteen**, and the reason it serves one is the
  material's own answer: of the mentor's forty-six comments on the first
  paper, the ones a later version really answered are few. **A memory that
  served all sixteen would be serving rules the chain cannot show to have
  been applied** — which is the difference between absorbing a mentor's
  judgement and arranging it. The owner ruled twice on what the material
  forced: **a judgement on the chain is a fact** (a second judgement does
  not undo the first, and a wrong judgement is corrected on the rule), and
  **the retrieval's threshold does not move**.
  [LC-P2-09 acceptance](../acceptance/LC-P2-09-acceptance.md) ·
  [the second corpus](../acceptance/second-corpus-absorption.md).

- **The consent machinery — the grant table, the two gates, and the
  refusals.** `access_grants` and `derived_copies` (migration
  `0011_access_grants.py`), the permission check that answers whether a use
  is permitted, the two independent gates a transmit request has to pass
  (the operation approval, and the grant that names the destination), the
  withdrawal and the propagation that reaches the copies derived from it, and
  the intake guards that refuse an archive **before it is opened**. **The
  absence of a row is the refusal**, and a refusal names the missing
  permission and what would satisfy it. The fourteen acceptance clauses each
  have a named witness, and an **independent review against the merged
  tree** found four properties that were true of the code and unwatched — a
  read grant answering a training use, the refusals that never reached a
  surface, an order that was not wired, and a demonstration that printed a
  claim it did not carry — **each of which now has a witness that fails when
  the property breaks**.
  [LC-P2-06 acceptance](../acceptance/LC-P2-06-acceptance.md) ·
  [the independent review](../acceptance/LC-P2-06-review.md).

- **The paper project and the version graph.** `paper_versions` and
  `version_edges` (migration `0010_paper_version_graph.py`), the contracts
  that hold them, the alignment that **proposes** an edge without deciding
  it, the human path that settles one, and the two checks that are about not
  lying about an archive. **A version graph and not a version list**: the
  process branches, so the parent lives in the edge table and the version
  table has no parent column. A confidence score is not a decision, and an
  unresolved relationship is a value rather than an absence.
  [LC-P2-08 acceptance](../acceptance/LC-P2-08-acceptance.md).

- **The OOXML-native reader.** `w:ins`, `w:del`, `w:commentRangeStart/End`
  and the rest, read out of the package itself rather than out of a
  converted document: `src/labcairn/material/ooxml.py`, with `DocxLocator`,
  `SourceKind.DOCX` and migration `0009`. **Revision recall 30/30, deletion
  recovery 8/8 and comment recall 14/14 on the synthetic corpus**, with four
  mutations applied to prove the witnesses fail for their properties.
  [LC-P2-07 fidelity baseline](../acceptance/LC-P2-07-fidelity-baseline.md).

- **The phase's work orders, folded into one ticket.**
  [`docs/plans/PHASE_2-work-orders.md`](../plans/PHASE_2-work-orders.md)
  merges the phase's two work-order lists into one ticket: **what is built,
  where each piece's record is, and the six pieces that are left** — the
  frozen P1 baseline the exit gate's denominator needs and does not have,
  the blind evaluation that is written and not run, the peer-review loop's
  judgement half, citation identity, retrieval quality beyond three papers,
  and the competitor comparison whose precondition has now been met. The two
  drafts it came from stay in the tree as the record of how the phase was
  planned, and every acceptance clause and file-ownership map in them is
  still the one its piece was built under.

- **The G1/G2 human review has a checklist.**
  [`docs/acceptance/G1-G2-human-review-checklist.md`](../acceptance/G1-G2-human-review-checklist.md)
  gives a named reviewer every clause of the two gates with the node id that
  holds it, the mutation that must go red, the commits each gate has taken since
  it closed, the three exit demonstrations with their check counts re-counted
  from the source (36 / 14 / 18), and the four places the two records are
  weakest — starting with the fact that four of G1's thirteen clause rows and all
  six of LC-P1-07's were recorded **by behaviour, not by node id**. **It carries no
  verdict**: the owner's ruling stands that the two AI retro-review rounds are
  procedural independence, not human, so the board's rule for G1 and G2 stays
  open until a person executes it.
  `tests/test_status_consistency.py::test_the_human_review_checklists_node_ids_exist`
  resolves every id the checklist cites — `::` continuations included — against
  the class the citation names, which is what a reader typing the id does.
  Writing the checklist produced three wrong ids by hand (`TestApprovalGate` for
  `TestApprovalCheckpoint`, a `tests/test_recovery_probe.py` that never existed,
  and two methods cited under the wrong class), and the first version of this
  check missed the third because it asked whether each segment exists *anywhere*
  in the file. Bare-file citations are still unchecked, and the witness says so.

- **The deterministic figure has a surface.** `labcairn task figure` and
  `POST /analysis` call the layer's own `run_figure`; `labcairn task
  approval-request` and `labcairn task approval-grant` are the consent it needs,
  because `recipe` is now one of `analysis.run`'s consented arguments — a
  signature covers the bytes the figure is drawn from, not only the material
  (ADR-0012 constraint 7). The run path no longer takes a recipe beside the
  consent it spends.

- **The report has a surface.** `labcairn task report --path report
  [--template default] [--json]` and `POST /report` on the local service both
  call the application layer's own `render_report` and answer with its own
  `ReportRendered`, so the bytes a CLI writes and the bytes the service serves
  are one artefact. A fresh workspace's policy now permits `report.render`, which
  the registry binds to output roots. **The workbench asks for it too**: a button
  that states the two claims the service takes no default for, then reads the
  artefact list again — and shows the service's own refusal when the task has
  nothing to carry. **The workbench asks for the figure's consent too**: a
  Figure panel builds the selection from the source the service reports, asks
  for `analysis.run`, leaves the pending question in the Approval panel, and
  draws once it is granted. Two steps are the design. The report is still
  refused — writing nothing — when the task holds no record to carry, which is
  the correct answer rather than a gap: the next bullet is the operation that
  records one.
- **A task can be given a claim to carry.** `labcairn task claim` and
  `POST /claims` call the layer's `record_claim`, which resolves the address in
  the text the ledger holds for the source's current bytes, refuses one nothing
  answers, and writes an anchor and an `extracted` record as the user's own.
  `labcairn sources addresses` and `GET /sources/{source_id}/addresses` list the
  addresses a claim can rest on. **What it does not do** is extract, propose or
  verify: the caller supplies the words, and no surface runs C1, C2 or C3.
  [release notes §2.2](../RELEASE-NOTES.md).
- **The recovery pass runs at the surfaces.** `run_stage` calls
  `labcairn.application.recovery.reconcile_abandoned` after the policy verdict and
  before any consent is spent: an operation a crash left `ATTEMPTING` becomes
  `UNCERTAIN`, its stage is blocked with the recovery layer's reason, and the next
  `task run` or `POST /stages` is refused with `operation_uncertain` rather than
  planning a second operation for the same work. `labcairn task reconcile
  <operation-id> --expected-sha256 <hash>` is the operator's half, because the
  value a probe needs is not recoverable from the store. **The limit that
  remains** is stated in [ADR-0003 C2](../adr/ADR-0003-event-and-permission-model.md)
  and in [release notes §2.18](../RELEASE-NOTES.md).
- **The approval ledger asks the capability registry.** Both consume paths refuse
  an id the registry has never held, with a reason of its own
  (`capability_unregistered`), which closes the defence-in-depth gap G1 recorded.

**Changed**

- **§1.4.1b is the harness's behaviour, not a note beside it.** The owner ruled
  on 2026-10-29, and `tests/evaluation/aggregate.py` now classifies every
  non-passing case by **what the skip's own reason says**: a fact of the machine
  (an OS, a filesystem, a volume with no 8.3 short names) and a test in a class
  the owner ruled discharged outside the offline run are **accepted**, a file the
  run did not select and a file in which pytest collected no case are named as
  what they are, and **any other skip fails the blocker** — for a blocker's own
  witnesses and for the sixth blocker's required CI tests alike. Accepted
  exclusions are printed in the row — a witness case by its node id and pytest's
  own reason, a required CI test by its file under the category it fell in.
  Scope: the owner
  chose **all blockers**, not only the sixth, which is what the second blocker's
  Windows row needed. `docs/EVALUATION.md` is not amended — this is the harness's
  reading of one clause, recorded so it can be checked.

**Fixed**

- **A test class's cases are keyed to the file that holds them.** pytest writes
  the module and the test class in one dotted `classname`, and the JUnit reader
  assumed there was no class, so `tests.test_skill_ledger.TestDigests` became
  `tests/test_skill_ledger/TestDigests.py` — a path that is not in the tree. Six
  files in this suite hold their cases in classes, and their cases entered no
  denominator: the `unsupported-claim-detection` metric reported **34/34** witness
  cases where the tree held **82**. The reader now takes the module from the tree
  (the longest dotted prefix that is an actual file), the test class stays in the
  node id, and `tests/evaluation/runner.py` names the tree it is reading. The
  same class is kept when a report carries a `file` attribute (pytest's legacy
  JUnit family writes one), so switching `junit_family` cannot reintroduce the
  collision. And the blockers table's column that counts cases which did not
  pass — three, on the second blocker, all of them accepted platform skips — now
  says **"Cases that did not pass"** instead of a bare *"Cases"*, because a HELD
  blocker beside the number 3 invites exactly the wrong reading.
- **Three CI shard files that collect nothing are reported as such.**
  `test_store_support.py`, `test_recovery_support.py` and `test_skill_support.py`
  are support modules other tests import; they are filed in a gate class and listed
  in the shard list on both platforms — in **one shard each**, not in every shard,
  which is what this entry printed until 2026-11-12 — and pytest collects no case
  in them. The blocker's row used to say
  the run "did not select" them. It now says no case was collected, which is the
  finding — **and whether a required test file that carries no case belongs in
  the shard list is carried to Phase 2 rather than settled here.**

- **The Windows case-fold now has a witness that bites.** The G1 regression test
  `test_a_deny_on_the_resolved_spelling_beats_an_allow_on_the_declared_one` asserted
  only `permission is DENY`, which a broken fold still satisfies: `evaluate` matches
  both spellings and the pre-resolved lowercase key hits the deny rule with no
  folding, so replacing `_FOLD` with the identity left the whole suite green. The
  Windows branch now also asserts `matched_spelling == "declared"` — the only
  observable that distinguishes a real case-fold from none. Verified by mutation on
  a Windows runner: passes under `str.casefold`, fails under the identity
  (`matched_spelling` reads `resolved`). It bites on the `windows-latest` shard,
  where the case-insensitive filesystem that makes the bypass possible actually
  exists; the POSIX early return stays, because there the two spellings are
  genuinely different files.

- **The real-provider smoke could not have run, and now it can.** The skipped
  witness in `tests/test_provider_credentials.py` hard-coded a protocol and a
  model and passed `environ={}` to the credential loader, so **no credential on
  any machine could have satisfied it** — the records that said "removing the
  skip runs it with no new code" were wrong. The probe now lives in
  `tests/test_real_provider_smoke.py`, the file the evaluation harness had been
  naming as the protocol's fifth gate class since LC-P1-13 T04 without one ever
  existing, and it is configured by `LABCAIRN_PROVIDER_SMOKE_KEY` / `_MODEL` /
  `_PROTOCOL` / `_BASE_URL`. It **ran twice on 2026-10-28** against
  `MiniMax-M3.1-Flash` over an Anthropic-protocol endpoint: `tool_calls` and
  `usage_reporting` **ok**, both structured-output forms **unsupported** in
  pydantic-ai's client before a request is sent. **The gate class is discharged
  by a job of its own, not by the required checks**: the required checks name no
  credential and one never will, because a check that can only pass where a
  secret exists is a check branch protection waits on forever — so
  `.github/workflows/provider-smoke.yml` holds it and runs on a schedule and on
  demand, and fails rather than skipping when a variable is missing — and it has
  run: dispatch 40663728369 at `0adfbe3`, 2026-10-28, printing the same endpoint
  fingerprint as the two local runs. The
  predicate that decides whether the witness runs is witnessed in the unit class
  (`tests/test_provider_credentials.py:309` and
  `tests/test_provider_credentials.py:355`), and `requires_provider` was added to
  the marker-to-class mapping so
  the fifth class is reachable by construction rather than unreachable in prose.
  **The harness's own veto went with it:** `--classes real_model_smoke` printed
  the runnability table's sentence about the environment — *"no real provider
  credential is configured in this environment"* — without looking at the
  environment, and invoked nothing, so no reader with a credential could
  discharge the class. Naming it now runs it; the default run still refuses it,
  and both halves are pinned
  (`tests/test_evaluation_harness.py::test_a_class_named_on_the_command_line_is_run_rather_than_refused`,
  `::test_the_default_run_reports_the_real_model_class_as_not_run`). Measured: the
  named run says **`1/1`** with the credential and `0/1` without it.
  [release notes §2.7](../RELEASE-NOTES.md).
- **The competitor baseline's real blocker is now a test, not a sentence.** After
  the credential landed, the question was whether the §5.1 harness change —
  carrying a provider's model into the run basis — was the next step. Reading the
  code says no: the compared numbers come from the deterministic corpus layer, not
  a model, so the run basis declaring `model=""` is the accurate fact, and
  threading a model the run never used would manufacture the exact
  "rate-without-a-limitation" the protocol forbids. The refusal is now executed
  (`tests/test_evaluation_harness.py::test_the_offline_run_refuses_a_competitor_on_the_model_alone`)
  with a control proving the same baseline becomes comparable the instant a
  model-declaring run exists
  (`::test_a_model_declaring_run_makes_that_same_competitor_comparable`). The gate
  on any comparison is a **model-driven answer path in the product** — Phase-2
  work, not a harness edit. [LC-P1-13 baseline §5.1](../acceptance/LC-P1-13-baseline.md).
- **The competitor live run measured both sides and reports comparable on all
  six conditions.** On 2026-11-04, under the owner's USD 50.00 approval, both
  sides ran `MiniMax-M3.1-Flash` over the same packaged corpus: the product's
  refusal rate and token cost versus the competitor's, with the aligner
  refusing a missing case, a misfiled artifact, a key pin mismatch, or a
  method outside the closed table. The rendered section names no winner and
  carries no ranking word; a reader can re-run one side and get the same
  figure. Token counts land in the closed table; USD spend is the owner's
  bill.
  [Live run](../acceptance/LC-P2-18-live-run.md) ·
  [machinery](../acceptance/LC-P2-18-machinery.md)
- **A reader can decode an `operation_reconciled` row without loading the
  recovery layer.** `ReconciliationPayload` and its registration moved to
  `labcairn.runtime.event` — the module the read boundary already imports — so
  the schema no longer depends on the coordinator having been imported in the
  same process. Before the move, a direct reader (a diagnostic script, a test
  calling `events_after`) was refused by the anti-bag rule on a row the writer
  had accepted. Witness: `tests/test_event_payload_vocabulary.py` reads the
  stored event in a fresh interpreter that loads no `labcairn.recovery` module;
  with the registry entry removed, that read fails with the pre-fix message.
  [ADR-0007](../adr/ADR-0007-event-payload.md).

