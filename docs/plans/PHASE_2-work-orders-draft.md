# Phase 2 — the first work orders, as a draft

**Status:** draft, written 2026-10-29 at the owner's request during the Phase 1
closeout. **Nothing here is dispatched**: no branch, no ADR, no board row. The
roadmap's rule is that a phase's detailed work orders are issued *"based on
implemented reality"* only after the previous phase closes
([`docs/ROADMAP.md`](../ROADMAP.md), Review protocol item 4), and Phase 1's last
owner ruling — §1.4.1b — landed at `16517e6`, so the ground is now real enough to
write on.

**What this list is for.** Six tickets, in the order they have to happen, each
with what it needs before it starts, what it costs, and how it is known to be
done. Two of them are not Phase 2 features at all — they are Phase 1 debts the
owner scoped here on 2026-10-28 and 2026-10-29, and they are listed as such
rather than dressed up as new capability.

---

## 1. What Phase 2 is for, in the roadmap's own words

> **P2 — Scientific Intelligence.** Better retrieval, citation
> identity/support, advanced analysis sandbox, higher-fidelity scientific plots,
> editing, expanded research Skills, conditional reviewers/subagents.
> **Exit gate:** *measured capability gain against a frozen P1 baseline, no
> scientific-claim inflation.*

Two things in that line govern every ticket below, and both are load-bearing:

- **Phase 2 items are upgrades, not first deliveries.** The deterministic plot
  (LC-P1-10) and the first-party `research-report` Skill (LC-P1-07) already ship
  and are `PASS WITH NOTES`. A Phase 2 ticket that re-delivers one of them has
  mis-read the phase.
- **"Measured capability gain" needs a number to measure against**, and there is
  no such number yet. That is why **LC-P2-00 comes first**: without a frozen
  baseline, the exit gate is a sentence rather than a test.
- **The hard principle holds across the phase:** *"Phase 2/3 features do not
  excuse failure of Phase 1 boundaries."* Every ticket below inherits the
  permission boundary, the consent digest, the evidence-locator contract and the
  evaluation protocol unchanged, and each says in its own words which of them it
  touches.

---

## 2. The order, and why

```
LC-P2-00  Freeze the P1 baseline          ─────────┐
                                                    │ (the exit gate's denominator)
LC-P2-02  Restart-durable consent   ──┐             │
                                      ▼             ▼
LC-P2-01  The model-call path  ──────────────────────────────┐
                                      │                       │
                                      ▼                       ▼
LC-P2-03  Competitor baseline (3 tasks)      LC-P2-04  Citation identity & support
                                                            │
                                                            ▼
                                              LC-P2-05  Retrieval quality
```

- **LC-P2-00 has no prerequisite** and everything else eventually compares to it.
- **LC-P2-02 before LC-P2-01** is not a dependency — it is the order that costs
  less. A model call that spends money is the first operation where *a consent
  that must not be re-spendable after a restart* matters in production rather
  than in a durability test; wiring the store first means the model path lands on
  a consent mechanism that already survives a crash.
- **LC-P2-03 is gated on LC-P2-01, and the gate is not administrative.** The
  comparison the harness prints today is between figures that come from the
  deterministic corpus layer, so a run basis naming a model would be a number
  about a model that no code produced. That wall is witnessed, not described:
  `test_the_offline_run_refuses_a_competitor_on_the_model_alone` and its control
  `test_a_model_declaring_run_makes_that_same_competitor_comparable`
  ([`LC-P1-13-baseline.md §5.1`](../acceptance/LC-P1-13-baseline.md)). Until a
  product operation actually calls a model, every honest comparison says what
  §2.8 of the release notes already records in its own words — *"No comparison has
  been made"* — and what the board's LC-P1-13 row and §1.4.3's Option C decided.
  **The owner confirmed §1.4.3 on 2026-10-29** (the board's ruling block), so the
  deferral is a ruling now rather than the work's own choice.

---

## 3. The tickets

### LC-P2-00 — Freeze the Phase 1 baseline

| | |
|---|---|
| **Objective** | One committed document holding the harness's measured figures at a named Phase 1 commit, in the shape `evaluation.comparison.load_baseline` reads, so "measured capability gain" has a denominator that cannot move underneath it. |
| **Prerequisite** | None. §1.4.1b's ruling (2026-10-29) is what makes the figure stable to read. **What is measured:** the same class of platform skips held the second blocker down on the Windows run recorded at `c362317` — three witness cases, *"the POSIX half of a platform pair, and the two 8.3 short-name witnesses"* — and that record says of them that **"no single runner of the CI matrix carries all of them."** **What is not measured:** no POSIX-side run is on record, so the mirror-image claim would be an inference. A frozen baseline therefore names its commit **and** its platform, and the re-measured Windows run at `22e2f2d` is the one §8 of the evaluation record carries now. |
| **Cost** | Small: one `python -m tests.evaluation` run, one document, and the six basis fields the comparison needs. |
| **Acceptance** | `python -m tests.evaluation --baseline <doc>` reports the comparison **comparable** with all six conditions met; the rendered section prints pairs and names no winner; the existing refusal witnesses stay red against a doctored basis. **Every figure in the frozen document names the commit and the working tree it was measured on** — the report already carries both, and the witness `test_the_report_says_when_the_tree_it_measured_was_dirty` is what makes a dirty-tree figure visible rather than implied. |
| **What it must not do** | Carry a model name the run did not use, or a cost the offline run did not spend. Both are `NOT MEASURED` today and the baseline says so in those words. |

### LC-P2-02 — Restart-durable consent

| | |
|---|---|
| **Objective** | Make the DB-backed `ApprovalStore` the path the product spends from, instead of the in-memory `ApprovalLedger`, so a granted approval is single-use **across a restart** rather than across one process. |
| **Why it is here and not in Phase 1** | The owner scoped it to Phase 2 on 2026-10-28. It is **a durability feature, not a safety hole**: today, after a restart the ledger is empty, so spending a granted approval fails closed with `APPROVAL_MISSING` rather than double-spending. |
| **Prerequisite — measured, not assumed** | `ApprovalRow` ([`src/labcairn/db/models.py:418-435`](../../src/labcairn/db/models.py)) carries `capability`, `resource_key`, `args_digest`, `state`, `expires_at`, `granted_at`, `consumed_at`, `schema_version` — and **no grant-time policy digest and no bound-source column**. `ApprovalStore.consume` takes both of those **as arguments** rather than reading them from the row, so the store as written is not itself restart-durable for the two checks that make a consent mean something. Migration head is `0008_c2_profile`; this needs `0009`. |
| **Scope of the change** | (a) the migration and the two columns; (b) reconciling event and row ownership so `request` / `grant` / `consume` do not double-emit into the append-only event table; (c) replacing the in-memory ledger the surfaces build — **one construction site**, [`cli/workspace.py:636`](../../src/labcairn/cli/workspace.py), inside the `application_context` builder at `:609` — per request on the service's forked session ([`api/routes.py:614`](../../src/labcairn/api/routes.py) is `context.store.fork().session`, and `routes.py:120` states the rule); note that the only other construction passes `_unused_ledger()` (`application/tasks.py:130`), whose own docstring says the ledger is never read, because creating a task has nothing to approve; (d) reworking the accepted G2 tests that inject `now=` or peek the ledger, which is the part that reopens consent internals the gate already accepted. |
| **Cost** | Large. It touches the store, the application layer, both surfaces and the accepted G2 test base. |
| **Acceptance** | A crash matrix case that kills the process between grant and consume and shows the **second** spend refused **from the row**, not from memory; the policy digest and the bound sources are read from the row rather than passed in; `ApprovalLedger` is either gone or is a cache that cannot outlive its row; and the single-use guarantee's existing witnesses stay red under the same mutations that make them red now. |
| **What it must not do** | Soften ADR-0003 C4's eight refusal reasons (seven at G2's close; `capability_unregistered` joined on 2026-10-27 in `26ab4cb`), or let a restart turn a spent approval back into a grantable one. |

### LC-P2-01 — The model-call path in the product

| | |
|---|---|
| **Objective** | One product operation that asks a **declared** model and records what came back, under the existing consent, budget and refusal machinery. |
| **The gap it closes, measured** | `providers/` speaks three real protocols and probes four capabilities, and a credential exists **as a CI secret for the probe job** — while Phase 1 configures **no provider for the product**, which `labcairn doctor` reports as an empty provider list ([`RELEASE-NOTES.md`](../RELEASE-NOTES.md)). So the only code in this repository that sends a real request is the probe (`tests/test_real_provider_smoke.py`, `labcairn providers probe`). `grep -n provider src/labcairn/skills/*.py` returns nothing: **no stage of the shipped `research-report` Skill calls a model**. Everything the three surfaces do today is deterministic. |
| **Prerequisites** | LC-P2-02 (so a paid call cannot be re-spent after a restart); **declaring `httpx`**, which today arrives transitively through `pydantic-ai` and is in no `dependencies` list (§2.13) — the provider path runs on it, so it must be a version this project chose; the ADR-0006 outbound-consent bridge, because this is the ticket that finally makes an unapproved outbound call possible through a surface; an ADR for the new capability id, because the capability registry is what the ledger checks before it spends (`capability_unregistered`); and the provider-selection question — the workspace's `providers.json` is the format `load_providers_config` reads, so the ticket does not invent a second one. |
| **Cost** | Medium-large, and **it spends money**: the owner's authorisation is a precondition, not a footnote. The probe's measured answer (2026-10-28, `MiniMax-M3.1-Flash`) is that `tool_calls` and `usage_reporting` work and **both structured-output forms are declined by the client**, so a design that assumes native structured output starts from a refusal. |
| **Acceptance** | The call is **consented** (an unapproved model call refuses with a machine-readable reason and does not spend); **budgeted** (a ceiling it cannot measure fails closed, which `test_cost_ceiling_fails_closed_when_price_unknown` already establishes for the layer); **recorded** (transcript and usage land in the store and in the report's hash chain); **refused** on an answer it cannot decode; and **any claim it makes is bound to a locator** before it can reach a report — the protocol's third blocker and ADR-0004 say a model's say-so is not evidence, and *"no scientific-claim inflation"* is half the phase's exit gate. |
| **What it must not do** | Become a second consent path. The digest is recomputed at the moment of use over the capability's canonical arguments; a ticket that mints its own approval has shipped an authorisation bypass. |

### LC-P2-03 — The competitor baseline, three tasks

| | |
|---|---|
| **Objective** | The comparison Phase 1 deliberately did not make: the same three tasks run against selected upstream systems, printed as pairs with the protocol's superiority clause respected. |
| **Prerequisite** | LC-P2-01, and the reason is in §2 above: our compared figures today come from the corpus layer, so naming a model in the basis would fabricate a comparison. The owner's decision of 2026-10-29 keeps §2.8's *"no external comparison"* in force **until this ticket starts**. |
| **Cost** | Money (provider spend on both sides of the comparison), a task corpus that is the same three tasks for every system, and the like-for-like basis the six conditions require. Upstream clones are already pinned by SHA in `UPSTREAM_REFERENCES.md`, with the standing force-push risk noted there. |
| **Acceptance** | `assess` returns comparable on all six conditions; the rendered section names no winner and carries no ranking word (both watched); the baseline document names its commit, its tree state, its model and its cost; and a reader can re-run one side and get the same figure. |
| **What it must not do** | Report a gain that is a difference in the corpus rather than in the system. That is what the six conditions exist to catch. |

### LC-P2-04 — Citation identity and support

| | |
|---|---|
| **Objective** | The P2 focus area *"citation identity/support"*, and simultaneously the half of LC-P1-09's acceptance clause that was never built. |
| **The gap** | Recorded as structural, not an oversight: **the fabricated-DOI half has no implementation, because no record can carry an identifier, nothing resolves one, and ingestion records none** ([`acceptance/LC-P1-09-acceptance.md`](../acceptance/LC-P1-09-acceptance.md), carried in the roadmap's open-issues list). Reports cite locators only, which is ADR-0004's contract, not a shortcut. |
| **Prerequisites** | A schema decision (an identifier column set, and who may write it), and a resolver with a refusal path — an identifier that cannot be checked must not become evidence. |
| **Cost** | Medium. It is a schema change plus the checks that make an unverified identifier different from a verified one. |
| **Acceptance** | An identifier can be recorded, is reported with its verification state, and **a claim may not rest on an identifier nothing resolved** — which is the same family as `test_a_claim_may_not_rest_on_a_conflicted_record`. C1/C2/C3 name the difference between "cited" and "supported". |
| **What it must not do** | Let a model-supplied DOI count as a citation check. That is claim inflation wearing a locator. |

### LC-P2-05 — Retrieval quality beyond three papers

| | |
|---|---|
| **Objective** | The P2 focus area *"better retrieval"*, measured rather than asserted. |
| **The gap, measured** | `tests/fixtures/retrieval/ground_truth.json` is a **human reading of three papers**, and the protocol's `evidence-locator-validity` metric is `NOT MEASURED` because the tree holds no human-checked citation-support sample over produced reports ([`acceptance/LC-P1-13-evaluation.md`](../acceptance/LC-P1-13-evaluation.md), the four metrics' reasons). The trigram index and the miss semantics exist; what does not exist is a corpus large enough that a retrieval improvement is a number rather than an anecdote. |
| **Prerequisites** | LC-P2-00 (a gain needs a before), and labelled data — which is a person's time, not a compute bill. |
| **Cost** | Labour: reading papers and recording addresses a human checked. Everything after that is cheap. |
| **Acceptance** | The metric is **measured**, with its denominator named and its sample size stated in the row (the harness already says when a denominator is small); a retrieval change moves the figure and the frozen baseline shows it moved; and the miss path stays honest — a query the index cannot serve is reported as a miss, not as an answer. |
| **What it must not do** | Report recall over a corpus the retriever was tuned on. |

---

## 4. Carried Phase 1 debt, scheduled rather than inherited

These are not Phase 2 capability. They are things the closeout found and did not
fix, listed with what each one costs if they keep being inherited.

| Item | Where it is recorded | What leaving it costs |
|---|---|---|
| **Three files in the CI shard list collect no test case** — `test_store_support.py`, `test_recovery_support.py`, `test_skill_support.py`, all support modules other tests import | [the evaluation record §8](../acceptance/LC-P1-13-evaluation.md), the board's carried-issues row | CI pays to collect them on every shard on both platforms; the partition's witnesses ask *"is every test file in a class?"* and never *"is there a test in it?"*, so nothing notices. Either rename them out of the `test_*` glob — which also takes them out of the shards — or stop calling them required tests. |
| **Nothing in CI runs the evaluation harness** | `python.yml` runs plain sharded pytest; `grep tests.evaluation .github/workflows/*` returns zero hits | The blocker table and the metrics exist only when someone runs them locally. Wiring them in is a **gate decision** (a failing blocker then blocks a merge), and it is the owner's: after §1.4.1b the run exits 2 because the fifth gate class cannot run offline, so a naive gate would be permanently red. |
| **One landed effect leaves two operation rows** | ADR-0003 C2, asserted in `tests/test_fault_injection_e2e.py` | A reader of the operation table sees two attempts for one effect. Stated, not silent. |
| **The workbench's four limits** — the event stream is not consumed by the UI; it cannot switch the selected project; it is never driven against the live service; the product has no operation that extracts a claim or accepts a model's proposal | LC-P1-12's board row, `RELEASE-NOTES.md` §2 | *"CLI and UI show identical Task state"* stays discharged through the API rather than measured, and the claim a report carries is made by a demonstration rather than by the product. LC-P2-01 changes the second one: the first model call makes "who extracts the claim" a live question. |
| **`httpx` is not a declared dependency** — it arrives transitively through `pydantic-ai`, and both the credentials and the provider-factory modules flag it | [`RELEASE-NOTES.md` §2.13](../RELEASE-NOTES.md), confirmed against `pyproject.toml` | LC-P2-01's provider path runs on it. A transitive version is not this project's to pin, so the model-call ticket would inherit an unpinned dependency of the exact layer it exists to exercise. |
| **`ArtifactLedger` is in memory** — LC-P1-07's ledger does not survive a restart, though the store does | `CURRENT.md`'s remaining-items list, the G2 entry | The same durability shape as LC-P2-02 on the artefact side: an artefact recorded before a restart is not the artefact a report reads after it. LC-P2-02 should say whether it takes this on or names why it does not. |
| **ADR-0006's outbound-consent bridge is not built** — both modules exist, nothing joins them | `CURRENT.md`'s remaining-items list, the G1 entry | *Unapproved outbound transmission* is a Phase 1 boundary the bridge would enforce rather than describe, and LC-P2-01 is the ticket that first makes a real outbound call possible through a surface. |
| **A read still takes SQLite's write lock** — every transaction opens with `BEGIN IMMEDIATE` | [`RELEASE-NOTES.md` §2.17](../RELEASE-NOTES.md) | Bounds how long a forked per-request session may be held, which is exactly the shape LC-P2-02's (c) and any concurrent surface work design around. |
| **The report's second revision is not recomputed from the revised material**, and **the DOCX and the PDF are not byte-reproducible** | [`RELEASE-NOTES.md` §2.3 and §2.15](../RELEASE-NOTES.md) | Two limits any *higher-fidelity plots / editing* ticket will be measured against: a claim of a rendered improvement has to say which of these it closes. |
| **The upstream pin SHAs were obtained from a shallow local clone** | the board's carried-issues row | Contradicts LC-P2-03's acceptance that *a reader can re-run one side*: re-verifying each pin with `git ls-remote` is a precondition of the comparison, not a nicety. |
| **Path-guard tests ran on Windows only** — POSIX alternate-data-stream and case semantics are unverified | `CURRENT.md`'s remaining-items list, the G1 entry | After §1.4.1b a platform skip is **accepted and named** rather than fatal, which makes an unverified half easy to mistake for a covered one. It is not covered; no runner has ever run those cases. |
| **The Gitleaks allowlist guard is textual, and the README capability-claim detector has known holes** | `CURRENT.md`'s remaining-items list, the cross-gate entries | Both are stated floors, not truth-checkers. Inheriting them is fine; describing them as a check that would catch a leak is not. |
| **The G1/G2 human review is prepared and unexecuted** | [`acceptance/G1-G2-human-review-checklist.md`](../acceptance/G1-G2-human-review-checklist.md) | The board's independence rule stays unsatisfied for the two oldest gates, and every gate after them inherits their contracts. |

---

## 5. Not tickets

- **The licence and copyright ownership.** The owner's, blocked on nothing in the
  code, and it gates any open-source claim rather than any feature
  (`LICENSE.PENDING.md` grants no rights).
- **Spending money on a provider.** Always the owner's authorisation, expressed
  as the four `LABCAIRN_PROVIDER_SMOKE_*` variables the CI job holds, and nothing else. (A fifth, `..._RECORD`, exists and is optional: it writes the probe's record outside the checkout.)
- **A sixth gate.** Phase 1 ran G0–G5; which of these tickets a gate closes
  over, and what its exit test is, is the owner's call and is deliberately not
  proposed here.

## 6. What each ticket needs before it can start

The Phase 1 pattern worked and this list should keep it: a work order gets a
**task breakdown with a file-ownership map** before code, its acceptance clauses
are written as clauses before the tests that carry them, and a gate closes on an
**independent review at a named commit** — the rule G1 and G2 are still waiting
on. No ticket above should be dispatched without its ADR slot decided first,
because the capability registry and the append-only event vocabulary are the two
places where two work orders have already made one answer impossible twice
(LC-P1-03's two capability vocabularies, and the source id's type in G4).
