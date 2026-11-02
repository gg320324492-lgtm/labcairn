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
| **The three-role loop** | the roles, the cards, the run, the refusals | [`LC-P2-12-acceptance.md`](../acceptance/LC-P2-12-acceptance.md) |
| **The model-call path** | one consented, budgeted, recorded, refusal-honest call | [`LC-P2-01-acceptance.md`](../acceptance/LC-P2-01-acceptance.md) |
| **Restart-durable consent** | the approval that survives a restart and cannot be spent twice | [`LC-P2-02-acceptance.md`](../acceptance/LC-P2-02-acceptance.md) |
| **The issue-key outlet** | the chain's own keys, read out of the chain | [`LC-P2-16-acceptance.md`](../acceptance/LC-P2-16-acceptance.md) |
| **The second corpus** | another paper, another advisor, thirty-four more comments | [`second-corpus-absorption.md`](../acceptance/second-corpus-absorption.md) |

**And the material is in the product, not in a folder.** Two pilot
projects, twenty versions, eighty comments, **1528 recorded changes**,
**1439 of them changes rather than marks**, and **32 judgements** of which
**two hold** — the owner's own. **The memory serves one rule and reports
fifteen**, and the chain's own listing says which of the eighty comments
nobody answered, which are waiting for a judgement, and which were
judged and did not answer.

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

**This is the whole of what is left, in the order it has to happen.**

| | what is missing | why it is missing | what it costs | how it is known to be done |
|---|---|---|---|---|
| **1** | **The frozen P1 baseline** | **LANDED (2026-11-02)** — [`LC-P2-00-baseline.md`](../acceptance/LC-P2-00-baseline.md) freezes the baseline at `81babd5`; when it was missing, the phase's exit gate could not be judged: *"measured capability gain against a frozen P1 baseline"* had **no baseline document in the tree** — the harness can read one and nothing supplied it | **small**: one evaluation run, one JSON document naming its commit, its platform, its tree state, its model and its cost | `python -m tests.evaluation --baseline <doc>` reports the comparison **comparable** on all six conditions, the rendered section names no winner, and the refusal witnesses stay red against a doctored basis — all three hold, measured against [`LC-P2-00-baseline.json`](../acceptance/LC-P2-00-baseline.json) |
| **2** | **The blind evaluation and ablation** | the phase's exit gate, and P2-AMD-01's law: without a controlled experiment on unseen papers the system cannot be said to have learned the advisor's thinking. **The protocol is written** ([`LC-P2-14-ablation-protocol.md`](LC-P2-14-ablation-protocol.md)), **the mechanical preparation is built** ([`LC-P2-14-preparation.md`](../acceptance/LC-P2-14-preparation.md): five arms as data, the by-paper leak check, the anonymous blind sheet, the paired sign test whose not-significant verdict is first-class — 64 witnesses, 47 self-reported mutations and 4 independent ones, all caught), **and the real run has not happened** | **the most expensive thing in the phase**: human blind rating, plus five arms' worth of model calls | a frozen set split **by paper**, the same model and a comparable budget across five arms, the two contrasts that matter (**D vs C** and **E vs D**) measured, and **"if the gain is not significant, that is reported as not significant"** |
| **3** | **The peer-review loop** | **done.** The reply table, the settlement over a reply (migration `0020`, `settle_reply`), the refused-or-held response whose claimed experiment the manuscript does not contain, the unsettled listing, the placed change, and a disagreement shown as **two sides** — all merged and recorded in [`LC-P2-09-acceptance.md`](../acceptance/LC-P2-09-acceptance.md) §10, and independently reviewed | — | each of those four is a witness; **acceptance is not proof the advice was scientifically right**, and that is the clause most likely to be got wrong |
| **4** | **Citation identity and support** | **done.** A record can carry a scholarly identifier with its provenance (ingestion/person/model), resolution is a state — `not_attempted` is **recorded, never sent** — a claim may not rest on an identifier nothing resolved, and a model-supplied identifier is not a citation check. [`LC-P2-17-citation-identity.md`](../acceptance/LC-P2-17-citation-identity.md) and the `test_identifier_records.py` witnesses; independently filed in the harness's manifest | — | an identifier can be recorded, is reported with its verification state, and **a claim may not rest on an identifier nothing resolved** — and **a model-supplied DOI may not count as a citation check** |
| **5** | **Retrieval quality beyond three papers** | the focus area *"better retrieval"*, measured rather than asserted. **The corpus is a human reading of three papers** and the protocol's `evidence-locator-validity` metric is `NOT MEASURED` because the tree holds no human-checked citation-support sample over produced reports | **labour**: reading papers and recording addresses a human checked. Everything after that is cheap | the metric is **measured** with its denominator named and its sample size stated, a retrieval change moves the figure and the frozen baseline shows it moved, and **a query the index cannot serve is reported as a miss, not as an answer** |
| **6** | **The competitor baseline** | the comparison Phase 1 deliberately did not make: the same three tasks run against selected upstream systems. **The task brief is written** ([`LC-P2-18-competitor-baseline-brief.md`](LC-P2-18-competitor-baseline-brief.md)) and runs nothing: the frozen offline baseline cannot be our side, so our side needs a real-model frozen run by LC-P2-00's procedure, and paper-qa is the only qualifying candidate so far | **money** (provider spend on both sides), a task corpus identical for every system, and the like-for-like basis the six conditions require. **Its precondition is met** — LC-P2-01 landed, and the frozen baseline exists | `assess` returns comparable on all six conditions, the rendered section names no winner and carries no ranking word, and **a reader can re-run one side and get the same figure** |

**And the second paper's rules are unserved for a reason the chain can
say.** Its three versions have **no version edge** — the material does not
say which came first, so the chain does not order them — and a change
travels an edge. **Its eight rules are therefore not in the chain's reach
as it stands**, and the memory reports them as unserved. **This is a
material gap, not a product one**, and it is closed by material, not by
code.

**And one reader defect is owed to the fidelity line.** The reader
records **one change twice in one file** (243 reported, 239 real), and the
revision event's id rests on an assumption that is false as written —
*the element's path is unique inside a part*. **It holds today only
because the four duplicates are the same change**; two **different**
changes sharing a path would lose one of them silently.

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
| **Nothing in CI runs the evaluation harness** | `python.yml` runs plain sharded pytest | the blocker table and the metrics exist only when somebody runs them locally. **Wiring them in is a gate decision and it is the owner's** — after the Phase 1 ruling the run exits 2 because the fifth gate class cannot run offline, so a naive gate would be permanently red |
| **The workbench's four limits** — the event stream is not consumed by the UI; it cannot switch the selected project; it is never driven against the live service; the product has no operation that extracts a claim or accepts a model's proposal | LC-P1-12's board row | *"CLI and UI show identical Task state"* stays discharged through the API rather than measured |
| **ADR-0006's outbound-consent bridge is not built** — both modules exist, nothing joins them | the G1 entry | *unapproved outbound transmission* is a Phase 1 boundary the bridge would enforce rather than describe |
| **`ArtifactLedger` is in memory** — the store does not survive it | the G2 entry | an artefact recorded before a restart is not the artefact a report reads after it |
| **A read still takes SQLite's write lock** — every transaction opens with `BEGIN IMMEDIATE` | the release notes §2.17 | bounds how long a forked per-request session may be held |
| **The report's second revision is not recomputed from the revised material**, and the DOCX and PDF are not byte-reproducible | the release notes §2.3 and §2.15 | two limits any higher-fidelity rendering ticket is measured against |
| **Path-guard tests ran on Windows only** | the G1 entry | a platform skip is **accepted and named** rather than fatal, which makes an unverified half easy to mistake for a covered one |
| **The Gitleaks allowlist guard is textual**, and the README capability-claim detector has known holes | the G1/G2 entries | both are stated floors, not truth-checkers |
| **The G1/G2 human review is prepared and unexecuted** | [`G1-G2-human-review-checklist.md`](../acceptance/G1-G2-human-review-checklist.md) | the board's independence rule stays unsatisfied for the two oldest gates, and every gate after them inherits their contracts |
| **The upstream pin SHAs came from a shallow local clone** | the board's carried-issues row | contradicts the competitor baseline's acceptance that *a reader can re-run one side* |

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
