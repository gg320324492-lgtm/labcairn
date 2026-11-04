# Phase 2 — one work order

**Status:** written 2026-11-01, at the owner's request to fold the phase's
work into one ticket. **It replaces the two drafts it came from** —
[`PHASE_2-work-orders-draft.md`](PHASE_2-work-orders-draft.md) (six
tickets) and [`PHASE_2-mentor-trajectory-work-orders.md`](PHASE_2-mentor-trajectory-work-orders.md)
(nine more) — which stay in the tree as the record of how the phase was
planned, and as the acceptance clauses and file-ownership maps each piece
was built under.

**What changed and what did not.** The numbering is retired: the phase
was planned as seventeen tickets (`LC-P2-00` … `LC-P2-16`) and is built
as **one line of work with one exit gate**. **Every acceptance record
stays where it is**, because a clause that was written before its witness
is the project's own rule and a record that moves is a record that stops
being read.

---

## 1. What the phase is for, and how it is judged

> **P2 — Scientific Intelligence.** Better retrieval, citation
> identity/support, advanced analysis sandbox, higher-fidelity scientific
> plots, editing, expanded research Skills, conditional reviewers/subagents.
> **Exit gate:** *measured capability gain against a frozen P1 baseline, no
> scientific-claim inflation.*

**And the phase's own route changed on 2026-10-31** (P2-AMD-01): **the
learning is retrieval, not training.** The advisor's judgements are read,
distilled, confirmed and retrieved; the model is a cloud model behind
three roles; **nothing is trained**, and the trajectory is searched rather
than fitted. The impact matrix is
[`P2-AMD-01-impact-matrix.md`](P2-AMD-01-impact-matrix.md).

**The gate has a denominator, and the denominator does not exist yet.**
"Measured capability gain" needs a frozen P1 baseline to compare against,
and **there is no baseline document in the tree** — the harness can read
one (`evaluation.comparison.load_baseline`) and nothing supplies it. **So
the phase's exit gate cannot be judged today, and this is the first
unfinished thing below.**

**And the phase's second law is the one the material tested.** *"没有在未见
论文上的对照实验，就不能宣称系统「学会了导师的科研思想」"* — without a
controlled experiment on unseen papers, the system cannot be said to have
learned the advisor's scientific thinking. **The material answered this
one honestly rather than conveniently**: of the mentor's forty-six
comments on the first paper, the ones a later version really answered are
**three or four**, and the memory now serves **one rule of sixteen** and
reports the other fifteen. **A memory that served all sixteen would be
serving rules the chain cannot show to have been applied** — which is the
difference between absorbing the mentor's judgement and arranging it.

---

## 2. What is built, and where the record is

| | what it is | the record |
|---|---|---|
| **The consent layer** | the grant table, the two transmit gates, the refusals | [`LC-P2-06-acceptance.md`](../acceptance/LC-P2-06-acceptance.md) |
| **The DOCX reader** | revisions, comments, anchors, locators | [`LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md) |
| **The version graph** | `paper_versions`, `version_edges`, and the seam that reads a manuscript's tracked changes | [`LC-P2-08-acceptance.md`](../acceptance/LC-P2-08-acceptance.md) |
| **The feedback chain** | the four rings: comment, change, judgement, assessment | [`LC-P2-09-acceptance.md`](../acceptance/LC-P2-09-acceptance.md) |
| **The annotation** | the label set, the guide, the gold set and two independent readings of it | [`LC-P2-10-acceptance.md`](../acceptance/LC-P2-10-acceptance.md) |
| **The guidance memory** | rules as versioned rows, candidates, confirmations, retrievals | [`LC-P2-11-acceptance.md`](../acceptance/LC-P2-11-acceptance.md) |
| **A rule from a tracked change** | the distillation's second case: a marked-up manuscript with hundreds of revisions and **no comment at all** is material a rule can be drawn from, the case key is the product's, the proposer is `operator_proposal`, and a rule read from too little is **rewritten under its own id** rather than duplicated beside itself. Held on nine changes and then run at size: **897 changes across five marked-up copies produced seven groups, six confirmed** | [`LC-P2-11-revision-distillation.md`](../acceptance/LC-P2-11-revision-distillation.md) · [the fourth pilot](../acceptance/LC-P2-11-pilot-4-distillation.md) |
| **A check that decides a rule** | the question a reader runs against a manuscript and what answers it, bound to the rule's **version**; exercised on real material for the first time — two rules, two confirmed checks, and the refusal that a candidate check cannot decide a rule proved on the row | [`LC-P2-11-check-binding.md`](../acceptance/LC-P2-11-check-binding.md) |
| **An assessment about a case that exists** | the fourth ring's door. `feedback_id` was guaranteed by a foreign key and `issue_key` by nothing at all — the column carries no key, because a case is a comment *or* a change and the two live in different tables — so the door resolves the key **by looking, never by spelling**, in the same order the retrieval takes, scoped to the project. Eight witnesses, five mutations (the fifth, breaking only the comment route, was not in the author's battery), and the ring itself **still holds zero rows** | [`LC-P2-11-assessment-door.md`](../acceptance/LC-P2-11-assessment-door.md) |
| **Did the later draft bear it out?** | the fourth ring opened: five assessments written through the door, every one `not_established`, three graded `observed` because the next draft carries the commented paragraph **byte for byte** and two `inferred` because the passage moved. The finding is the funnel, not the five: of 32 comment keys, **14 have no anchored words and 9 sit on the newest draft**, so **five of the sixteen comment-derived rules could be judged**; and of the eight revision-derived rules **none** can, because all thirty of their cases are the advisor writing his instruction as a new paragraph — no earlier wording, no corresponding place. **Re-measured 2026-11-04 after the SOW (2) data correction** (store at `0023`): the anchor test now fails **12 of 32**, and **six** comment-derived rules are judgeable — the re-anchored deletion-collapse rows gave one more rule its first readable anchor. The fifth and sixth assessments' recording is the owner's call. | [`LC-P2-11-fourth-ring.md`](../acceptance/LC-P2-11-fourth-ring.md) §1 |
| **The material's words out of the records** | the public repository carried the owner's unpublished corpus in three documents -- a 76-character distilled rule statement, the manuscript paragraph a tracked change was made in, two advisor comments and the group's own writing template named in its words -- under a sentence in `CURRENT.md` that asserted the opposite. Replaced by length and digest with the store address; watched by a per-file pin that reddens on growth **and on a carried-forward number**, and by a policy cap of 14 that a re-measurement cannot satisfy. Six mutations, five caught; the sixth, which raises the cap itself, is stated as the limit rather than hidden | [`LC-P2-11-material-words-out-of-the-records.md`](../acceptance/LC-P2-11-material-words-out-of-the-records.md) |
| **The three-role loop** | the roles, the cards, the run, the refusals | [`LC-P2-12-acceptance.md`](../acceptance/LC-P2-12-acceptance.md) |
| **The model-call path** | one consented, budgeted, recorded, refusal-honest call | [`LC-P2-01-acceptance.md`](../acceptance/LC-P2-01-acceptance.md) |
| **Restart-durable consent** | the approval that survives a restart and cannot be spent twice | [`LC-P2-02-acceptance.md`](../acceptance/LC-P2-02-acceptance.md) |
| **The issue-key outlet** | the chain's own keys, read out of the chain | [`LC-P2-16-acceptance.md`](../acceptance/LC-P2-16-acceptance.md) |
| **The second corpus** | another paper, another advisor, thirty-four more comments | [`second-corpus-absorption.md`](../acceptance/second-corpus-absorption.md) |

**And the material is in the product, not in a folder.** Two pilot
projects, twenty versions, **eighteen version edges** (the second
paper's edges built from the timestamps inside the material itself —
the advisor's comments of 03-07, the author's revision of 03-12, the
second advisor's both of 03-16), eighty comments, **1819 recorded
changes** — the whole of what the files record, the marks an operation
at a point leaves behind having been shown to be absent from the
count —, **36 correspondences** of which **2 hold, 8 do not and 26
wait for a judgement**, and one reply settlement. **The memory serves
one rule and reports fifteen**, and the chain's own listing says which
of the eighty comments nobody answered, which are waiting for a
judgement, and which were judged and did not answer.

**The owner ruled on two things the material forced** (2026-11-01), and
both are in the code, the record and the review points:

- **A judgement on the chain is a fact.** A second judgement on the same
  correspondence does not undo the first, and a judgement that turns out
  to be wrong is corrected **on the rule** — withdrawn, disputed or
  superseded — and not on the chain.
- **The retrieval's threshold does not move.** The rule is served on a
  source a judgement says was answered, and the owner kept that after
  seeing what the material says about it.

---

## 3. What is not built, and what each piece costs

**This is the whole of what was left, in the order it has to happen — and a
row that is closed stays in place, marked.** Deleting it would make the table
read as though the work had never been owed, and the ordering is what says
which piece unblocks which. **Read the second column for the state**: a row
that says LANDED or done is history with its evidence, and the rows that
describe a cost still being owed are the ones the phase is waiting on.

| | what is missing | why it is missing | what it costs | how it is known to be done |
|---|---|---|---|---|
| **1** | **The frozen P1 baseline** | **LANDED (2026-11-02)** — [`LC-P2-00-baseline.md`](../acceptance/LC-P2-00-baseline.md) freezes the baseline at `81babd5`; when it was missing, the phase's exit gate could not be judged: *"measured capability gain against a frozen P1 baseline"* had **no baseline document in the tree** — the harness can read one and nothing supplied it | **small**: one evaluation run, one JSON document naming its commit, its platform, its tree state, its model and its cost | `python -m tests.evaluation --baseline <doc>` reports the comparison **comparable** on all six conditions, the rendered section names no winner, and the refusal witnesses stay red against a doctored basis — all three hold, measured against [`LC-P2-00-baseline.json`](../acceptance/LC-P2-00-baseline.json) |
| **2** | **The blind evaluation and ablation** | the phase's exit gate, and P2-AMD-01's law: without a controlled experiment on unseen papers the system cannot be said to have learned the advisor's thinking. **The protocol is written** ([`LC-P2-14-ablation-protocol.md`](LC-P2-14-ablation-protocol.md)), **the mechanical preparation is built** ([`LC-P2-14-preparation.md`](../acceptance/LC-P2-14-preparation.md): five arms as data, the by-paper leak check, the anonymous blind sheet, the paired sign test whose not-significant verdict is first-class — 64 witnesses, 47 self-reported mutations and 4 independent ones, all caught), **and the real run has not happened** | **the most expensive thing in the phase**: human blind rating, plus five arms' worth of model calls | a frozen set split **by paper**, the same model and a comparable budget across five arms, the two contrasts that matter (**D vs C** and **E vs D**) measured, and **"if the gain is not significant, that is reported as not significant"** |
| **3** | **The peer-review loop** | **done.** The reply table, the settlement over a reply (migration `0020`, `settle_reply`), the refused-or-held response whose claimed experiment the manuscript does not contain, the unsettled listing, the placed change, and a disagreement shown as **two sides** — all merged and recorded in [`LC-P2-09-acceptance.md`](../acceptance/LC-P2-09-acceptance.md) §10, and independently reviewed | — | each of those four is a witness; **acceptance is not proof the advice was scientifically right**, and that is the clause most likely to be got wrong |
| **4** | **Citation identity and support** | **done.** A record can carry a scholarly identifier with its provenance (ingestion/person/model), resolution is a state — `not_attempted` is **recorded, never sent** — a claim may not rest on an identifier nothing resolved, and a model-supplied identifier is not a citation check. [`LC-P2-17-citation-identity.md`](../acceptance/LC-P2-17-citation-identity.md) and the `test_identifier_records.py` witnesses; independently filed in the harness's manifest | — | an identifier can be recorded, is reported with its verification state, and **a claim may not rest on an identifier nothing resolved** — and **a model-supplied DOI may not count as a citation check** |
| **5** | **Retrieval quality beyond three papers** | the focus area *"better retrieval"*, measured rather than asserted. **The corpus is a human reading of three papers** and the protocol's `evidence-locator-validity` metric is `NOT MEASURED` because the tree holds no human-checked citation-support sample over produced reports. **The machinery is built (2026-11-04)** ([`LC-P2-26-retrieval-metric-machinery.md`](../acceptance/LC-P2-26-retrieval-metric-machinery.md)): a five-field sample table whose loader refuses any sixth field (a text field is the leak channel), an empty sample that measures `NOT MEASURED` and never a 0/0 rate, and the run handed a filled table with `--citation-sample` — a filled table lives outside this public repository, because it carries addresses into the manuscript | **labour**: reading papers and recording addresses a human checked, then recording one row per citation. Everything after that is now built | the metric is **measured** with its denominator named and its sample size stated, a retrieval change moves the figure and the frozen baseline shows it moved, and **a query the index cannot serve is reported as a miss, not as an answer** |
| **6** | **The competitor baseline** | the comparison Phase 1 deliberately did not make: the same three tasks run against selected upstream systems. **The task brief is written** ([`LC-P2-18-competitor-baseline-brief.md`](LC-P2-18-competitor-baseline-brief.md)) and runs nothing, and **the machinery is built (2026-11-04)** ([`LC-P2-18-machinery.md`](../acceptance/LC-P2-18-machinery.md)): one packaged task corpus both sides consume byte-identically, a paper-qa runner whose live mode refuses without the owner's approval file (dry mode plans the calls for zero spend), an aligner that refuses a missing case, a misfiled artifact, a key pin that does not match, or a method outside the closed table, and the runbook the owner executes on approval | **money** (provider spend on both sides — the one remaining input, the owner's approval), declared identically on both sides through the runner's approval file | `assess` returns comparable on all six conditions, the rendered section names no winner and carries no ranking word, and **a reader can re-run one side and get the same figure** |

**And the second paper's rules are unserved for a reason the chain can
say.** Its three versions have **no version edge** — the material does not
say which came first, so the chain does not order them — and a change
travels an edge. **Its eight rules are therefore not in the chain's reach
as it stands**, and the memory reports them as unserved. **This is a
material gap, not a product one**, and it is closed by material, not by
code.

**And the reader debt that was owed to the fidelity line is paid.** It was
two things, and they were opposite failures. The reader recorded **one
change twice in one file** (243 reported against 239 elements) — fixed in
`f4a7e94`, and that draft now reads 239 events against 239 distinct
addresses. And the revision event's id rested on an assumption false as
written — *the element's path is unique inside a part* — which held only
because every duplicate happened to be the same change; **two different
changes at one path would have lost one of them silently**. The id is now
keyed `(version, part, element_path, occurrence)`, with the first change at
an address keeping the digest every stored row already carries, so the 2164
pilot rows and the rules bound to them do not move
([`LC-P2-07-revision-event-identity.md`](../acceptance/LC-P2-07-revision-event-identity.md)).
The third case was the reverse of the first: a table row's insertion marker
(`w:trPr/w:ins`) sits outside every paragraph, so a scan that walks
paragraphs **never reported it** — measured across all five corpora, 4499
revision elements against 4498 reported, one file short. The reader now
reports it, with `paragraph` absent rather than invented
([`LC-P2-07-table-row-markers.md`](../acceptance/LC-P2-07-table-row-markers.md)).

---

## 4. What this phase does not do

- **The licence and copyright ownership.** The owner's, and it gates any
  open-source claim rather than any feature.
- **Training.** P2-AMD-01 removed it: the route is a cloud model, three
  roles and trajectory retrieval. **Prompt optimisation and fine-tuning**
  (the old LC-P2-15) are off the critical path and nothing in this line
  waits for them.
- **A sixth gate.** Which piece closes over which gate, and what its exit
  test is, is the owner's call.

---

## 5. Carried Phase 1 debt, still carried

These are not Phase 2 capability. They are things the Phase 1 closeout
found and did not fix, and they are listed here so that they are not
inherited silently:

| Item | Where it is recorded | What leaving it costs |
|---|---|---|
| ~~**Three files in the CI shard list collect no test case** — `test_store_support.py`, `test_recovery_support.py`, `test_skill_support.py`~~ | the evaluation record §8 | **Closed 2026-11-02.** They are not placeholders and nothing supersedes them: 47 test files import them (41 store, 4 recovery, 6 skill), so deleting them would break every importer, and folding them into their siblings would copy 1,244 lines of fixtures. They were **renamed out of the `test_*` glob** — the first of the two routes the Phase 1 board named — to `tests/store_support.py`, `tests/recovery_support.py` and `tests/skill_support.py`. Their shard entries (both platforms), cost entries and evaluation-manifest rows are gone; `test_evaluation_harness.py` still witnesses *collected nothing* with a synthetic selected-and-empty run; `python .github/make_ci_shards.py` re-balanced both partitions from the existing runner costs (Ubuntu 1.231, Windows 1.000), so no CI run was spent. |
| ~~**Nothing in CI runs the evaluation harness**~~ | `python.yml`'s `evaluation` job, and [`LC-P1-13-evaluation-ci.md`](LC-P1-13-evaluation-ci.md) | **Partly closed 2026-11-03.** A weekly scheduled job now runs the harness over the five offline classes, uploads the report and prints it in the log; `lint` and the shards are skipped on the schedule event, and the job is **not** a required check. **Still the owner's:** the trigger (weekly schedule, per-merge push on `main`, or a per-pull-request job that could be required) and whether the runner cost is acceptable; the job has not been measured on a runner, because GitHub fires a schedule only from the default branch. The fifth class is `NOT SELECTED` and is discharged by `provider-smoke.yml` under the 2026-10-28 ruling; a naive pull-request gate would still be permanently red, which is why the job is not one. |
| **The workbench's four limits** — ~~the event stream is not consumed by the UI~~; ~~it cannot switch the selected project~~; ~~it is never driven against the live service~~; ~~the product has no operation that extracts a claim or accepts a model's proposal~~ | LC-P1-12's board row | **Four closed 2026-11-02, each with a witness.** The Events panel consumes `/events/stream`, reports connecting/live/reconnecting/disconnected and resumes from its cursor (`web/src/views/EventsView.test.tsx`); the Projects panel switches the binding through `POST /task/select`, which writes the same `current_task` the CLI reads (`tests/test_api.py`, `web/src/app/workbench.test.tsx`); `tests/test_workbench_live_service.py` drives one running service — the CLI as a subprocess and the API over the in-process ASGI transport — and compares `GET /task` with `task status --json` field for field, before and after a selection; and the two evidence acts have routes: `POST /claims/extract` records a model's answer as a proposal (never a person's claim) and `POST /records/{evidence_id}/accept` calls `confirm_proposal` unchanged, with the Proposals panel posting both verdicts and re-reading `/records` (`tests/test_api.py`, `web/src/views/ProposalsView.test.tsx`). The owner's eight decisions and the witnesses are recorded in [`workbench-claim-extraction-and-proposal-acceptance.md`](workbench-claim-extraction-and-proposal-acceptance.md) §3–§4. |
| ~~**ADR-0006's outbound-consent bridge is not built** — both modules exist, nothing joins them~~ **CLOSED (2026-11-02)**: the provider is handed an `OutboundConsent` decision and cannot be constructed without one; `send` refuses before the transport when the decision is missing, expired or already spent — [`LC-P1-03-outbound-bridge.md`](../acceptance/LC-P1-03-outbound-bridge.md) | the G1 entry | *unapproved outbound transmission* is now enforced at the provider boundary, not described |
| ~~**`ArtifactLedger` is in memory** — the store does not survive it~~ **CLOSED (2026-11-02)**: `SqliteArtifactLedgerStore` writes through `artifact_ledger_entries` (migration 0022); a new instance on the same database reads the stored canonical payload back and re-hashes it — [`LC-P1-06-artifact-ledger.md`](../acceptance/LC-P1-06-artifact-ledger.md) | the G2 entry | an artefact recorded before a restart is the artefact a report reads after it |
| ~~**A read still takes SQLite's write lock** — every transaction opens with `BEGIN IMMEDIATE`~~ **CLOSED (2026-11-02)**: a read-only engine opens a deferred `BEGIN` and sets `PRAGMA query_only=ON`; the write engine still takes the write lock before its first read (C3's witness stays green) — [`LC-P1-06-sqlite-read-lock.md`](../acceptance/LC-P1-06-sqlite-read-lock.md) | the release notes §2.17 | a read is a snapshot and no longer bounds how long a per-request session may be held |
| ~~**The report's second revision is not recomputed from the revised material**, and the DOCX and PDF are not byte-reproducible~~ **CLOSED (2026-11-02)**: the report carries only the parts whose own chain names a material hash the ledger still holds, so the revision rendered after a re-ingest carries the run over the revised bytes; the DOCX's ZIP entries are stamped with the report's own `as_of`, so its bytes are reproducible — [`RELEASE-NOTES.md`](../RELEASE-NOTES.md) §2.3 and §2.15 | the release notes §2.3 and §2.15 | *"requests a revision"* is now discharged by recomputation, and the DOCX joins Markdown and HTML as a hash-comparable form; the **PDF stays recorded and not claimed**, by the owner's 2026-10-20 decision (breakdown §1.4.3, Option A) |
| ~~**Path-guard tests ran on Windows only**~~ **CLOSED (2026-11-02)**: the POSIX half is witnessed, and writing it found four misreports. The guard and its witnesses are at `e53db78` and `22dd085`. **Measured on Ubuntu 24.04 (WSL):** `tests/test_security_paths.py` is **48 passed / 15 skipped**, the 15 being the Windows-only semantics and named `Windows path semantics`; **on Windows the same file is 51 passed / 12 skipped**, the 12 being the POSIX witnesses (one parameterised three ways) and three pre-existing skips, named `POSIX path semantics`. **Per property:** *case* — POSIX admits `Case.txt` and `case.txt` as two keys, with distinct inodes asserted first; the Windows tests assert the opposite. *`:`* — a real `notes:draft.txt` is created and read back on POSIX, so its refusal is now `unrepresentable_key_character` (a key character set shared with Windows), not `alternate_data_stream`. *Trailing dot/space* — POSIX stores `report.txt.`, `report.txt ` and `report.txt` as three files and admits all three; Windows still refuses the aliases. *8.3 short names* — **not applicable on POSIX**; no equivalent is claimed. *Drive letters and UNC* — not POSIX syntax; `//server/share/x` is refused as `outside_every_root`, not `remote_root`. *Symlinks and `..`* — the resolved path decides, and `hop/..` is refused where lexical collapse would have admitted it. *`*` and `?`* — excluded from `ResourceKey`; refused on both platforms, and on POSIX the two files are created literally first, so the refusal is not a glob expansion. **Seven mutations, each run on Linux, made its witness red** (colon reason, trailing-dot condition, backslash condition, case folding, `//` condition, `resolve()` replaced by lexical collapse, `*`/`?` condition removed). **Not verified:** macOS is not on the CI matrix and is recorded as a difference only (HFS+/APFS is case-insensitive by default, NFD-normalising, and Finder maps `:` to `/`); and this is a WSL Ubuntu run, not a GitHub runner, so the Ubuntu shard remains the first runner measurement |
| **The Gitleaks allowlist guard parsed only the top-level `allowlists` array**, and the README capability-claim detector had the holes LC-P1-01 listed | `docs/acceptance/LC-P2-25-guard-of-the-guards.md` | **CLOSED 2026-11-02** — both carry witnesses now; the qualifier whitewash named in the same row is still open and is stated in the record |
| **The G1/G2 human review is prepared and unexecuted** | [`G1-G2-human-review-checklist.md`](../acceptance/G1-G2-human-review-checklist.md) | the board's independence rule stays unsatisfied for the two oldest gates, and every gate after them inherits their contracts |
| ~~**The upstream pin SHAs came from a shallow local clone**~~ **CLOSED (2026-11-02)**: all five clones were made full and each pin verified as an ancestor of its remote default branch, with the commands and the commits-after-pin recorded — [`UPSTREAM_REFERENCES.md`](../UPSTREAM_REFERENCES.md) §"verified against remote" | the board's carried-issues row | the competitor baseline's acceptance that *a reader can re-run one side* now has its precondition |

---

## 6. What has to happen before the next piece of code

**The Phase 1 pattern worked and this phase keeps it**: a piece gets a
task breakdown with a file-ownership map before code, its acceptance
clauses are written as clauses before the tests that carry them, and the
claims are **measured, not asserted** — a witness that stays green under
a mutation is either a survivor or a mutation that never took effect, and
the two are told apart by looking at what the code did.

**And the phase's own rule, which the material tested hardest**: **the
chain's records and the memory's numbers are the evidence, and a record
that says one thing while the store says another is corrected to the
store.**
