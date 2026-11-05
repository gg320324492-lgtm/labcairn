# LabCairn Four-Phase Roadmap

**Version:** LCR-PLAN-1.1  
**Synchronized with:** `LC-P1-v1.1`, the Phase 1 work orders and gates in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md). Phase plan and work orders are revised together; they must never drift apart.
**Status:** Phase 1 closed at G5; Phase 2's exit gate is CLOSED, PASS WITH
NOTES; later phases are strategic targets, not approved implementation work
orders.

## Current position

**Phase:** P2 — Scientific Intelligence · **Phase 1:** G0, G1, G2, G3, G4 and **G5 closed**; the last three closures rest on an independent review rather than on an owner decision — G3's at `d114810`, G4's at `9381036af0104172f16fe94a6edd2e8cb6d9ae04` and G5's at `72154cd`, verdicts **PASS WITH NOTES**, and for G5 the first scope's verdict moved from **FAIL** to **PASS** after its findings were fixed · see [`handoff/CURRENT.md`](handoff/CURRENT.md) for the authoritative pointer

| | |
|---|---|
| Completed | **LC-P1-00** — upstream source study, three architecture ADRs, pinned reference index. `PASS WITH NOTES`, reviewed at `623e3ca` and merged as PR #1 (`9b445cd`). Those are the **review subject and merge commit**, not the current tip. |
| Accepted and merged | **LC-P1-01 … LC-P1-14** — the engineering baseline (LC-P1-01), the trusted core (02–04, G1), the durable work and its recovery (05–07, G2), the evidence path (08 material and locators, 09 retrieval and the ledger, 10 bounded analysis and a deterministic figure), and the usable application (11 the report path, 12 the three surfaces behind the one application layer). **Every work order is `PASS WITH NOTES`**, each with its own acceptance review under [`acceptance/`](acceptance/), and every one of them was reviewed by the party that wrote the fixes — except **G3's three and G4's two**, which were also reviewed independently, at `d114810` and at `9381036af0104172f16fe94a6edd2e8cb6d9ae04`. |
| Next direction | **G5 is closed on two independent reviews, and it is the last of Phase 1.** **LC-P1-13** (the evaluation harness, the fault injection, the competitor baseline) and **LC-P1-14** (the public alpha handoff: the bilingual delivery documents, the release contents and the NOTICE, the review dossier, the licence audit). G5's exit test is *"outsider fresh install, 3 fixtures, fault injection, docs and real-provider smoke"*, and **four of the five are delivered and watched**: the outsider's path runs in a clean clone and is compared field by field, the three fixtures' answer keys are re-derived by code that is **not the product's**, the fault injection now goes **through the CLI and the service** and is killed at the process level, and the documents' commands are extracted and **run for real**. The fifth — the real-provider smoke — **has not run**: the harness reports it NOT RUN and exits 2, and **that is the owner's decision** (§1.4.2). **Two reviewers wrote none of the gate's fixes**; the first's verdict was **FAIL** on a property table that was entirely clean, and after every finding was fixed it **re-ran its own eleven mutations against the fixed code and passed**. **Twenty-four findings between them, all fixed**, and the gate found six more on its own. The [gate review](acceptance/G5-acceptance.md) records the method, both verdicts and what became of every finding. **What it handed over**: the surfaces never run the recovery pass, so a crash through the CLI leaves an operation `ATTEMPTING` for ever and the next run plans a second one — **the side effect is not duplicated**, so this is a repeated *operation* rather than a repeated *byte**, and it is asserted rather than left as a sentence. **That hand-over is closed after the gate** — see the carried-issues list below: the surfaces now run the pass, refuse the second plan, and leave the answering to `labcairn task reconcile`. **The gate is closed; Phase 2 is under way** — the phase's pieces are merged
as they land, **the mentor's own material is in the chain and the memory
serves one rule of sixteen**, and **the phase's exit gate cannot be judged
yet**: the frozen P1 baseline exists (`LC-P2-00`, at `81babd5`), but the
blind evaluation's human ratings and the retrieval metric's human sample have
not been produced. What is built and what is left is in [the phase's one work
order](plans/PHASE_2-work-orders.md).
| Previous direction | **G4 is closed on an independent review.** **LC-P1-11** (report assembly, export and artefact versioning) and **LC-P1-12** (the Typer CLI and the local FastAPI + React workbench), behind the one application layer they all call. G4's exit test is *"CLI and Web produce same versioned report"*, and it is **demonstrated**: the CLI's task document and the local service's are compared **field by field** (255 fields, none differing) and the report's **bytes by hash**, for each of the four forms, against the file the report operation wrote and the bytes the service serves. The gate's own commit is `9381036af0104172f16fe94a6edd2e8cb6d9ae04`: T00, the report's document model · ADR-0013, the export libraries · T05, the application layer · T02, the report artefact manifest · T01, the four renderers · T04, the content checks · T07, the local service · the layer's event read · the source id's type · T06, the Typer CLI · T03, the revisions and the staleness · T12, the document builder · T08, the React workbench · T13, the layer's report operation · T09, the end-to-end smoke path — and then the fixes the gate's own review and that demonstration found: the doctor's token file, the service's **session per request** (it shared one session across concurrent requests, and the workbench reads eight paths at once), **`labcairn serve`** (nothing started the local service at all), the **ingestion operation** (no surface could bind a material, so a report could carry only disclosures), the material walk's recorded path, the report's **material in its own chain** (a claims-only report could never be marked `STALE`), the Markdown's **whitespace**, and the refusals nobody watched · then the **two blockers and six notes** the three surfaces' review found — the demonstration's **exit code** was not load-bearing, a stage run that followed an approval **planned a second operation**, the CLI's prose form and its JSON form could disagree, the token was not compared in constant time, the event stream's session was asserted against the wrong session, three of the demonstration's comparisons could be narrowed, the binding's docstring stated a distinction the code could not express, and a module docstring denied an import the module made · and then the **five the fixing found**: a **time bomb in the gate's own exit demonstration** (it failed after 13:00 UTC, and no CI run had ever run after 13:00), a parked stage that raised a raw `IntegrityError`, a resumed run that could **attempt an effect nobody authorised**, a grant of a lapsed approval that reached the database as a raw `IntegrityError`, and a duplicated sentence in the demonstration's own output · and then the **four the last round found**: the rule that does the watching was not itself watched, one command-level refusal was watched by nothing, the pairing of a witness with the refusal it watches was itself unwatched, and the crash fix's catches were load-bearing and unwatched. LC-P1-11's and LC-P1-12's acceptance reviews are written, both **PASS WITH NOTES**, and **the gate's own independent review is what discharged the board's rule for both** — two reviewers who wrote none of the gate's fixes, one of whom **failed the gate five times on a clean property table** — its findings fixed and re-reviewed by itself each time — and the other of whom **came back BLOCKED five times and FAIL once**, the first on two blockers and six notes, one of the blockers sitting directly under the gate's own exit test, and the last, at `47259e0`, on **this round's four findings**. **Every finding is fixed**, and both reviewers re-ran their own mutations against the fixed code. **G3 is closed**, on the independent review at `d114810` — verdict **PASS WITH NOTES**: a reviewer that wrote none of the gate's fixes broke each of the gate's fourteen fixes in turn and **no mutation survived** ([gate review](acceptance/G3-acceptance.md)). No decision stands between the two gates. |

**Open issues carried forward** (full table with owners in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md)):

- Copyright ownership is unresolved and the repository deliberately has **no `LICENSE` file**. No open-source rights have been granted.
- ~~**The surfaces never run the recovery pass.**~~ **CLOSED after the gate**: `run_stage` calls `labcairn.application.recovery.reconcile_abandoned` after the policy verdict and before any consent is spent, so a crash through a surface leaves its operation `UNCERTAIN` with the stage blocked, and the next `task run` is **refused** with `operation_uncertain` rather than planning a second one. What a surface may not do is answer the doubt itself — the predicted hash is not recoverable from the store — so `labcairn task reconcile <operation-id> --expected-sha256 <hash>` is the operator's half, and a `CONFLICT` stays blocked and writes nothing. **The half that remains**: a probe can say the effect landed, but the interrupted transaction (confirmation, completed stage, receipts) is performed by the run that follows, so one effect leaves two operation rows. Recorded in [ADR-0003 C2](adr/ADR-0003-event-and-permission-model.md) and watched by `tests/test_fault_injection_e2e.py::test_a_task_continues_from_what_was_recorded_after_a_crash`.
- **The protocol's real-model smoke has not run as a standing witness**, and cannot here: no credential is configured in this tree, and Phase 1's **default offline run** reads no environment variable (the provider layer reads one, where a workspace's `providers.json` names it). LC-P1-03's own clause *"real smoke on at least one provider"* **was** met once by hand — `b237751`, 2026-10-16, on an owner-supplied credential — and that is the distinction the records kept collapsing: **the clause is met, the gate class is not discharged**. **None of the protocol's six Phase 1 blockers names a real provider**, and the sixth now says what a declared, recorded skip is — but the smoke itself is **still owed**, and it is the owner's to supply. **Updated 2026-10-28:** the class now has its witness file, `tests/test_real_provider_smoke.py`, and it **ran twice** on an owner-supplied credential (`MiniMax-M3.1-Flash` over an Anthropic-protocol endpoint; `tool_calls` and `usage_reporting` ok, both structured-output forms declined in the client). What is still owed is narrower than it was and it is still the owner's: a **CI secret**, so the class runs on a commit rather than on a machine.
- **PyMuPDF was avoided**: [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md) chose pdfplumber and pdfminer.six, both MIT, over PyMuPDF, whose AGPL branch would have constrained a future MIT release.
- Reference isolation **is now enforced on `main`** since `89c16d4`: `tests/test_no_reference_leakage.py` (99 tests) and `reference-exclusion` as a required status check. It was prose until LC-P1-01 merged.
- The five upstream pin SHAs were **verified present on GitHub at LC-P1-00 review time**. The standing risk is upstream force-push or garbage collection, which no local practice prevents; re-verify with `git ls-remote <url>` before relying on a pin.
- **The fabricated-DOI half of LC-P1-09's clause is still unimplemented**, and the gap is structural: the ledger holds no external identifier for a source, so a report can only cite locators unless G4 changes that.
- **G1's and G2's work orders still have no independent review.** The board's rule — a row is marked done only when an independent review at a named commit says so — is unsatisfied for them. **Corrected 2026-10-29, because the reason this line gave was wrong.** It said the reviews and the fixes *"were the same party in every case"*; the gates' own records say something narrower and less comfortable — *"A reviewer who did not implement any of this ran this document against the code. **This is internal cross-validation by two agents, not an external independent audit**, and is not evidence of one"* ([`G2-acceptance.md:98`](acceptance/G2-acceptance.md)), and [release notes §2.9](RELEASE-NOTES.md) calls it *"a reviewer who did not implement the work, but who was inside the project"*. So the reviewer was a different agent, and the rule is still unmet — because the reviewing party was inside the same project and session as the work, and because the owner ruled on 2026-10-28 that the two AI retro-review rounds since then are **procedural independence, not human** and do not discharge it. [`G1-G2-human-review-checklist.md`](acceptance/G1-G2-human-review-checklist.md) is what a named person works from: 33 clause rows with the node id and the mutation each one turns red, the commits both gates have taken since they closed, and the four places these two records are weakest. **Prepared 2026-10-29; not executed.** G3's three work orders have an independent review, at `d114810`, and the decision of 2026-10-18 that let LC-P1-08 proceed to LC-P1-09 without one was superseded on 2026-10-20, when the owner decided that the gate closes **after** an independent review rather than instead of one.
- ~~**The exit demonstrations of G1 and G2 are run by nothing**~~ **RESOLVED**: `tests/test_earlier_exit_demos.py` runs each of them as a subprocess, **with the exit code as the assertion**, and its own witness checks that a broken guard turns that code red. It was dark for three gates and the reason was a skip that outlived the defect it waited for (the gate's review, S6/R3). LC-P1-10's and G4's demonstrations were already covered.
- ~~**matplotlib's bundled fonts bring a licence obligation** that the root licence line does not cover~~ **MEASURED**: [the font audit](acceptance/LC-P1-14-font-licence-audit.md) checked what actually reaches a user and found **no third-party font file in any artefact** — the DOCX has a `fontTable.xml` and no `word/fonts/` part, the PDF **references** the core Type 1 faces rather than embedding any (`/FontFile`, `/FontFile2`, `/FontFile3` all absent), and the figure is a raster, so its text is pixels. The release gate's font check now watches by extension **set**, not by file name (the second review's R15).

**What is not yet true of this project:** `main` now holds a research workspace's **spine** — versioned contracts, a permission boundary, a durable task store with crash recovery, material ingestion with locators, a lexical index and an evidence ledger, bounded statistics with a deterministic figure, and a reproducibility manifest — **and all three of its surfaces**: the report's document model with its four renderers, the report artefact manifest that lists what a report is made of, the one application layer that the CLI, the local API and the web UI all call, the Typer CLI, the local FastAPI service, and the React workbench. **A research task now runs end to end from the CLI** — the smoke path (T09) does it from a clean workspace, with no network call and no credential — and the three surfaces produce the **same** report, which is G4's exit test · **what that demonstration did not exercise** is the React application: the workbench is driven through the API it reads, so *"CLI and UI show identical Task state"* is discharged **through the API** rather than measured between the two, and the claim the report carries **was made by the demonstration, not by the product**.

| Phase | Focus | Exit gate |
|---|---|---|
| P1 — Foundation & MVP | Standalone local-first Agent, typed tools, task/resume, evidence anchors, bounded analysis with a deterministic scientific plot, a first-party research Skill, report delivery, CLI + local Web | Fresh external install and end-to-end evidence-backed task, with security/recovery/quality tests |
| P2 — Scientific Intelligence | Better retrieval, citation identity/support, advanced analysis sandbox, higher-fidelity scientific plots, editing, expanded research Skills, conditional reviewers/subagents, **and the mentor-guidance trajectory line** (learning a paper's revision history, not its final text) | Measured capability gain against a frozen P1 baseline, no scientific-claim inflation |
| P3 — Production & Ecosystem | Stronger isolation, packaging, plugin/MCP trust, Windows/macOS/Linux distribution, robustness, observability, docs, benchmark expansion | Secure, maintainable, multi-platform public release and documented operational limits |
| P4 — Continuous Improvement | User feedback, targeted refinements, provider/format coverage, incremental UX/performance improvements | Small reviewable releases with regression tests and clear changelogs |

Phase 2 items listed against scientific plots and research Skills are **upgrades** of Phase 1 capabilities, not their first delivery. Phase 1 **delivers** a deterministic plot (`LC-P1-10`) and a first-party `research-report` Skill (`LC-P1-07`) — both are on the status board as `PASS WITH NOTES`; Phase 2 raises their fidelity and breadth.

### Phase 2 has two lines, and the owner ruled on both (2026-10-29)

**Line A — the six foundational tickets** in
[`plans/PHASE_2-work-orders-draft.md`](plans/PHASE_2-work-orders-draft.md)
(`LC-P2-00` … `LC-P2-05`): freeze the P1 baseline, restart-durable consent,
the model-call path, the competitor baseline, citation identity, and
retrieval quality.

**Line B — the mentor-guidance trajectory**, in
[`plans/PHASE_2-mentor-trajectory-work-orders.md`](plans/PHASE_2-mentor-trajectory-work-orders.md)
(`LC-P2-06` … `LC-P2-14`): the system learns how a paper was *corrected* —
the draft, the advisor's tracked changes and comments, the student's
response, the review, the outcome — and proposes guidance on a new paper it
has never seen.

**Three owner rulings, 2026-10-29:**

1. **Line B is part of Phase 2**, as an additional line. PR #125's six
   tickets keep their numbers and their scope, and neither line waits for the
   other.
2. **The pilot is a controlled single machine** with an offline intake
   directory, one administrator and a few invited annotators — ADR-0015 D6's
   assumption. **Not** a shared server: the multi-user identity and
   row-level access work is a later ADR, and opening a LAN or public
   service before it exists is out of scope.
3. **The first implementation is LC-P2-08** (the paper project and the
   version graph), because LC-P2-06's grant table names the paper project
   it covers, and because a revision event that nothing can store is a
   reading and not a record.

**What the ruling does not say.** It does not say the guidance agent
works. LC-P2-14 exists to find out, and its acceptance explicitly allows
the answer to be *"no measurable gain"*.

**Where Line B stands (2026-11-01).** **LC-P2-08** (the version graph),
**LC-P2-06** (the data governance), **LC-P2-09** (the feedback chain),
**LC-P2-10** (the process annotation and the gold set), **LC-P2-11** (the
guidance memory), **LC-P2-12** (the three-role loop), **LC-P2-01** (the
model-call path) and **LC-P2-02** (restart-durable consent) are merged,
**and the phase's two work-order lists are now one ticket**
([`plans/PHASE_2-work-orders.md`](plans/PHASE_2-work-orders.md)), which
says what is built and what is left.

**What LC-P2-10 settled, and what the later tickets read:** a closed vocabulary the chain's
own words come from, an annotation guide, a synthetic corpus whose every
item carries **two independent readings and an arbiter's row**, and an
agreement reported **with its denominator and with the readings that were
made without the labels kept in the tree**. **And what it did not
deliver:** the labels were written by sessions rather than by people, and
the pilot corpus is still the owner's.

**And what the mentor's own material settled, on 2026-11-01.** Two
projects, eighty comments, **1819 recorded changes** and **the owner's own
judgements** on ten correspondences: **two hold, eight do not**, so **the
memory serves one rule of sixteen and reports fifteen**. **The retrieval's
threshold did not move** — a rule is served on a source a judgement says
was answered — and **the chain's judgement is a fact**: a second judgement
on the same correspondence does not undo the first, and a wrong judgement is
corrected **on the rule**. The second paper's **eighteen version edges**
were built from the timestamps inside the material itself, on 2026-11-02.
**What was left at that date** is in the merged ticket: the blind
evaluation's real run (its machinery is built and mutation-verified
twice), retrieval quality beyond three papers (its machinery — the
citation-support sample's schema, loader, measurement and `--citation-sample`
wiring — is built and mutation-verified, 2026-11-04; the human pass over
produced reports is the part left), and the competitor
comparison.

**Where Line B stands (2026-11-02, later).** Everything the 2026-11-01
entry lists is merged, and more has landed since: **the reader reports
one tracked change once** (the drawing-text-box double-read, with the
shape in the corpus so the witnesses catch it by construction), **the
peer-review loop has its judgement half** (the settlement over a reply,
LC-P2-13), **the P1 baseline is frozen** (the exit gate's denominator,
measured on `81babd5`, six conditions verified comparable end to end),
**citation identity is built** (a record can carry a scholarly
identifier with its provenance, a claim may not rest on one nothing
resolved, and `not_attempted` is recorded rather than silently sent —
LC-P2-17), **the blind evaluation's mechanical preparation is built and
mutation-verified twice** (five arms as data, the by-paper leak check
that names every shape, the anonymous sheet that refuses an arm key,
the paired sign test whose not-significant verdict is first-class —
LC-P2-14's machinery), and **five acceptance
records carry an independent review** (every mutation re-applied by a
session that built none of them, every witness watched). **The first
unseen paper has since been assembled into those arms and the dry run
walked end to end on it** — 12 cases, 60 stub calls, zero provider calls,
the leak check run against the real chain and clean. **The owner approved
a real run on 2026-11-04, and a single-case calibration was run before
scaling**: three arms metered 52779 tokens against an estimated 10808,
so the estimate was wrong by 4.88x and scaling stopped by the owner's own
rule. The machine was then repaired — the shared-loop fault, approval
consumption before the wire, missing output policy and the arrangement
pair's runnable path — and one case was recalibrated: all five arms
answered at **27209 tokens** (8210 in, 18999 out), **48.45%** below the
old measurement but still **2.52x** the original estimate. The owner then approved the 12-case scaled run: all **84** calls
answered at **398555 tokens** (115337 in, 283218 out), 87.19% of the
457111-token hard ceiling, in 51.9 minutes. The five-arm B / arrangement
B-only item-id collision was found and repaired by adding a run scope
to the anonymous digest; the 84 paid-for answers were rebuilt into 84
distinct blind items without another provider call. **The machine side
is complete but the measurement is not**: no human rater sheets or
arbiter exist, so D vs C, E vs D and B+C vs B-only all remain `NOT RUN`
with no p-value or significance claim. A second unseen paper and the
human ratings remain owner-side work
([`LC-P2-14-unseen-material.md`](acceptance/LC-P2-14-unseen-material.md)).
**Of the merged ticket's six, four were built at that date and two were
left**: the blind evaluation's human scoring and second paper, and the
competitor comparison (brief written, preconditions met, budget and
final pick the owner's call). Retrieval quality beyond three papers waits
on a corpus read by a human, per LC-P2-14's own protocol.

**Where Line B stands (2026-11-05).** **Both unseen papers have been run
end to end, and the close-out that reads them is wired.** The second paper
(eight versions of one manuscript) dry-ran at **65 stub calls** and zero
provider calls; the owner approved the real run, which answered **91 of 91
calls** at **404802 metered tokens against a 577000 hard stop (70.16%)**,
zero truncations, after one calibration case measured **28850 tokens**
against paper 1's **27209** (**1.06x**, inside the declared **1.25x** stop
line) — commit `ee61e435ccf8a29513ee4b344e9d7a8d9d3ff625`. The close-out
assembles the second paper's **91 volumes** into two anonymous sheets (**13
per arm A–E, 13 `B-only`, 13 `B+critique`**, 91 distinct ids) while the first
paper's **84 volumes** read exactly as before; its witness file grew from
**99 to 107** — commit `6c77a018713bae1a5117e2f9099cb76717f11f21`, on the
machinery of `6ca09196a205db2e6727375b5be16543c9545f8e`. **The measurement is
not made**: no sheet is filled, no significance exists and no capability
claim follows.

**Batch 7 (review–response–revision) is in the tree as two negative
witnesses and a read-only route pilot.** The recon rule counts **432 / 66**
red runs; the pilot's own rule lands on **401 / 62**, and its store holds
**37 `replies` rows (29 + 8)**; no full ingestion was performed — measured at
`fc06cee7e79f20e831c9412f880e30fb323a8b30`, landed at
`8dff3360aab0d0f60890a3d58427441df711889c`. **The retrieval metric's
machinery is built but the metric is not measured**: a five-field sample
table whose loader refuses any sixth field, an empty sample that reports
`NOT MEASURED` and never a 0/0 rate, and a `--citation-sample` path — commit
`6ccdfcc41c35f132dcec299f5795c1e1793d655e`. **The competitor baseline has a
live run**: both sides ran under `MiniMax-M3.1-Flash` on a **USD 50.00**
budget, and the aligner reports **comparable — all six conditions met**; our
side scored **69/89** numeric exactness, **1/1** unsupported-claim detection
and **4/4** recovery, paper-qa **183/232** recall, **1/1** and **0/4**, on
different denominators and therefore with no task-1 pair — commit
`85424c5a5a27e5896ccc1ed4cd671b6a1b199250`. **The anchor that covers no text
is stored as covering no text**: `position` is a third status, schema `0023`
(commit `e7d58f8b0431be8ddf1d401585fa69066d3ea1cd`), and the SOW (2)
correction run on the real store on 2026-11-04 leaves **59 fresh / 21
unanchored / 0 stale over 80 rows**, with no empty-text `resolved` row and no
`sha256("")` digest anywhere — commits
`2fc7e03a3adf493b08052a818bc302bae940a4b2` and
`f876affc874047850f6506b021cdb41a4b7cda82`.

**Where Line B stands (2026-11-05, later the same day).** The close-out has
now run: both papers' sheets were filled by independent reader sessions, and
the owner decided on 2026-11-05 that an **independent agent session may stand
in for a human reader** (the records say the substitution, never that a human
read). Agreement **343/420** and **441/455**; 77 and 14 disputes settled by
third readers; **all 30 verdicts NOT SIGNIFICANT** — commit
`4aeb2fb822922d748531d5870290a3e1b56f82db`, decision
`8da3c55d568d9cb53b6ee25ba3605815d527754f`. **The G1/G2 checklist ran**: 33
rows, **21 A / 12 B / 0 C / 0 D**, the twelve B rows naming witness problems;
the independence clause is named as *not* discharged by that review — commit
`d63078c72b28c124852bece80a4ee4c422dd3706`. **The citation-support metric is
measured**: `evidence-locator-validity` **36/45** over a 45-row sample, with
the frozen P1 baseline predating the key so no pair prints yet — commit
`d959044c12dfbaa8493033960fea9f2e722da21e`. **The rule layer's third rule has
a confirmed check**, bound to version 1, with the unconfirmed-bind refusal
demonstrated on the real rows (the store holds 25 confirmed rules, 25 checks,
25 bindings) — commit `e248a6dfd7cd9bf0221b539e7ebe7e9343e343b8`. **Batch 8's
draft chain is a version graph** in the pilot store: 9 versions, 7
owner-accepted edges, 2,289 revision events, no rule distilled — commit
`1d328fd97f2b61d02aab396a8322e8fc8cc084ad`. **Batch 9's response letters
routed through `replies`**: 8 letters, 72 `Point` items (46 distinct), the
agriculture 20 pairs and MNB 24 pairs written to a fresh scratch store and
read back 44/44 with matching hashes; the mixed-source water-supply letter
was not touched, and the English revised manuscripts are absent from the
material — commit `c25bb6d8922c9e0bb6027d951d0786e110fa6541`.

**Where Line B stands (2026-11-05, end of day).** Phase 2's exit gate is
**CLOSED, PASS WITH NOTES**: the measured answer is *no capability gain*, 30
NOT SIGNIFICANT verdicts, with five notes attached — commit
`54ac69677658e7346677617c7c6e58df329a6c8d`. The locator baseline is frozen
over the filled 45-row sample (`evidence-locator-validity 36/45`, five offline
classes green, two independent readings agree 45/45) — commit
`d1278195b303aa9a57d8d7b02c51890a88b289c8`. An independent agent session
re-ran G1/G2 (19 A / 14 B / 0 C / 0 D), the four B-row witness gaps were
closed, and CEJ full ingestion was written as design only (`ADR-0020` +
LC-P2-28) — commits `925113d24d9b8732d50d2f296abd7e0b4c70da75`,
`eff2b68cb8dd1850a6f1ba5929aadedc2c419e0a`,
`a9d127484edf11e24ec3ee41217a54d2d872eae6`. **Batches 9 and 10 are in the
pilot store**: the water graph (3 versions / 1 unaccepted edge / 345
revisions / 5 comments), the eight-directory graph (8 versions / 7 unaccepted
edges / 17 OLE2 refusals / no fabricated events), four batch-9 negative
witnesses and three batch-10 negative witnesses. Batch 10's first two-gate
write stopped on a missing isolated `TEMP` directory, was rolled back
byte-for-byte, then succeeded — commits `ac8fe6fb6fd8cc945999b230962324d82c78669d`,
`131ce4bc4959e3a754be01643603a8f482f7e71e`,
`fc6d1dbfc7867810632e99680f08b3b054737e7f`,
`0e83aa9e523d3d949f9560cbee586d6c2c340214`,
`d19ea0412211e40e8c0bafdd684390c475dd2741`.
`main` is **35 commits ahead of `origin/main`**, unpushed by the owner's
choice; the licence, the CI provider credential and the next material batch
remain the owner's.

## Phase 1 upstream research

**LC-P1-00** is a new lightweight prerequisite and continuing reference task: establish separate local clones of selected top Agent/scientific-Agent repositories, record precise SHAs and license context, and use ADRs/tests to justify architecture choices. Do not vendor/reference-clone entire repositories inside the public repo. See [`UPSTREAM_REFERENCES.md`](UPSTREAM_REFERENCES.md). P1 now contains **15 work orders (00–14)**, with G0 for reference setup before the original G1–G5 gates.

## Review protocol

1. Complete all work orders and exit gates for the current phase. Internal commits and PRs may be used during the phase.
2. Push a verifiable GitHub commit SHA or PR, plus actual test results and demonstration evidence.
3. Independent reviewer examines source, contracts, tests, security and demonstration; statuses: PASS / PASS WITH NOTES / BLOCKED / FAIL.
4. Fix blocking findings before phase close. Only then issue the *next phase's detailed* work orders based on implemented reality.

**Hard principle:** Phase 2/3 features do not excuse failure of Phase 1 boundaries; security and evaluation start in Phase 1 and mature thereafter.
