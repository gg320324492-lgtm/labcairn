# Phase 3 - Design Traceability Proposal (Not Approved)

**Status:** Proposal for owner decision — not approved, not dispatched, not a work order
**Date:** 2026-11-06.
**Baseline:** `b3fba5f1581b066e64c2bc7b884ebc952605245d`, printed by `git rev-parse HEAD` before this draft was written. No other commit id is quoted.
**Companions:**
[`PHASE_3-execution-plan.md`](PHASE_3-execution-plan.md),
[`PHASE_3-scoping-pack.md`](PHASE_3-scoping-pack.md),
[`PHASE_3-planning-decisions-2026-11-06.md`](../acceptance/PHASE_3-planning-decisions-2026-11-06.md),
[`ROADMAP.md`](../ROADMAP.md),
[`CURRENT.md`](../handoff/CURRENT.md).

These relative links resolve from `docs/plans/` in the public repository; all five targets exist in the working tree. The Word and PDF source material, their extracted text and the Chinese working drafts remain outside the repository. The public repository keeps only English decision summaries, candidate work-package labels, acceptance language and a gap register. No source sentence, long scenario, example, personal name, unpublished material content or specific research-direction term is copied here; a synthetic research domain and a sample DOCX stand in for source examples.

Candidate labels became ticket ids on 2026-11-07: the owner decision record [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) adopts `LC-P3-00` through `LC-P3-08` as the formal numbering; `W10` through `W29` and `G0` through `G4` remain proposal labels until their own owner decisions. Adopting a label is not dispatch — a ticket starts only on the owner's word. Of the gaps recorded at Q76, Q77, Q81, Q82, Q86, Q87 and Q96, five were ruled that day (see `LC-P3-00` section 8); Q77 and Q82 remain. This file supplies no answers on the owner's behalf.

Status vocabulary: `CONFIRMED`, `SUPERSEDED_BY_LATER_QUESTION`, `RECOMMENDED_ONLY`, `ORIGINAL_MISSING`, `CONFIRMATION_MISSING`, `UNRESOLVED`. `RECOMMENDED_ONLY`, `ORIGINAL_MISSING` and `CONFIRMATION_MISSING` always appear with `UNRESOLVED`. Q23 -> Q57 and Q25 -> Q54 are the two superseded rows. Q36, Q47, Q59 and Q74 were confirmed later in the source material and are `CONFIRMED`.

## Engineering registration note

Any later test added for a candidate label must carry `pytestmark`, be listed in `.github/ci-shards.json` and be registered in `tests/evaluation/manifest.py`. This is a registration rule, not an instruction to add a test now.

## Candidate label legend

`LC-P3-00`, `LC-P3-01`, `LC-P3-02`, `LC-P3-03`, `LC-P3-04`, `LC-P3-05`, `LC-P3-06`, `LC-P3-07`, `LC-P3-08` are candidate work-order labels. `W10`, `W11`, `W12`, `W13`, `W14`, `W15`, `W16`, `W17`, `W18`, `W19`, `W20`, `W21`, `W22`, `W23`, `W24`, `W25`, `W26`, `W27`, `W28`, `W29` are candidate later work-package labels. `G0`, `G1`, `G2`, `G3`, `G4` are candidate gate labels. None is a ticket id; all require an owner decision record first.

## From question numbers to candidate work packages

| Question range | Candidate mapping |
|---|---|
| Q1-Q6 | Candidate: LC-P3-00, LC-P3-03, LC-P3-04, LC-P3-08, W17, W18. |
| Q7-Q9 | Candidate: W13, W15, W18, W21, W22, W23, W24, W25, W26. |
| Q10-Q14 | Candidate: LC-P3-05, W11, W12, W29. |
| Q15-Q20 | Candidate: LC-P3-03, W10, W14, W15, W18. |
| Q21-Q30 | Candidate: LC-P3-02, LC-P3-03, LC-P3-04, LC-P3-05, W12, W13, W16, W17, W28. |
| Q31-Q38 | Candidate: LC-P3-03, LC-P3-06, W10, W11, W14, W16, W29. |
| Q39-Q46 | Candidate: LC-P3-03, LC-P3-04, LC-P3-05, LC-P3-06, LC-P3-07, W13, W14, W17, W19, W22, W23. |
| Q47-Q53 | Candidate: W15, W18, W21. |
| Q54-Q63 | Candidate: LC-P3-01, LC-P3-02, LC-P3-03, LC-P3-04, LC-P3-05, LC-P3-07, LC-P3-08, W17, W28. |
| Q64-Q75 | Candidate: LC-P3-03, LC-P3-06, LC-P3-07, W10, W11, W12, W14, W16, W17, W19. |
| Q76-Q81 | Candidate: W13, W15, W18, W19; Q76 and Q81 were ruled owner decisions on 2026-11-07 (`LC-P3-00` section 8); Q77 has no stem or options recorded and stays unresolved at the memory-interface trigger. |
| Q82-Q87 | Candidate only: W20 or W25 for confirmed rows; Q86 and Q87 were ruled by owner segments on 2026-11-07 (`LC-P3-00` section 8); Q82 has neither stem, options nor conclusion anywhere and stays unresolved at the baseline-freeze trigger. |
| Q88-Q95 | Candidate: W22, W23, W24, W25, W26, W27. |
| Q96 (trigger only) | Before any project-workspace acceptance clause is written. |

## Question-by-question traceability

The `LC-P3-*` ids were adopted as formal ticket numbering by `LC-P3-00` on 2026-11-07; `W*` and `G*` landings stay proposal labels. Q1-Q96 rows are English topic summaries, not quotations.

| Question | Design topic | status | Candidate landing |
|---|---|---|---|
| Q1 | Shared advisor-and-student research platform. | `CONFIRMED` | Candidate: LC-P3-08, G4, W17, W18. |
| Q2 | Start with one research group, then broaden tenancy. | `CONFIRMED` | Candidate: LC-P3-00, W29, G4. |
| Q3 | Guidance and document evolution as the core loop. | `CONFIRMED` | Candidate: LC-P3-04, G2, G3. |
| Q4 | Capture guidance reasoning, limits and resolution steps. | `CONFIRMED` | Candidate: LC-P3-04, W15, W18, W21. |
| Q5 | Four support levels from diagnosis to execution. | `CONFIRMED` | Candidate: LC-P3-04, G2. |
| Q6 | Tiered autonomy with approval for high-risk edits. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-04, W10, W18. |
| Q7 | Separate personal, group, project and growth knowledge. | `CONFIRMED` | Candidate: W13, W15, W18, W21, W22, W23, W24, W25, W26. |
| Q8 | Stagewise archive for drafts, reviews and decisions. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-04, W22, W23. |
| Q9 | Neutral domain model for a synthetic research domain. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-06, LC-P3-08; a sample DOCX is the neutral fixture. |
| Q10 | Local client with controlled model access. | `CONFIRMED` | Candidate: LC-P3-05, LC-P3-06, W11, W12, W29. |
| Q11 | Desktop entry first, browser administration later. | `CONFIRMED` | Candidate: LC-P3-01, LC-P3-05, W28. |
| Q12 | Local-by-default files, authorised shared storage later. | `CONFIRMED` | Candidate: LC-P3-03, W11, W12, W29. |
| Q13 | Offline queue, restart recovery and separate backup. | `CONFIRMED` | Candidate: W11, W12, W29. |
| Q14 | Personal agent plus file-based handoff. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, W14, W15. |
| Q15 | Project-scoped visibility and isolation. | `CONFIRMED` | Candidate: LC-P3-03, W10, W14. |
| Q16 | Share only necessary versions, comments and progress. | `CONFIRMED` | Candidate: W10, W14, W15, W18. |
| Q17 | Exit handling preserves shared history and private bounds. | `CONFIRMED` | Candidate: W10, W14, W15. |
| Q18 | Layered guidance experience from cases to group rules. | `CONFIRMED` | Candidate: W15, W18, W21. |
| Q19 | Candidate experience requires review and validation. | `CONFIRMED` | Candidate: W15, W18, W21. |
| Q20 | Record disagreement, evidence and applicability. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, W21. |
| Q21 | Stepwise confirmation and delegated execution. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-04, G2. |
| Q22 | Prefer formal interfaces and controlled adapters. | `CONFIRMED` | Candidate: LC-P3-02, W10, W11, W16, W17. |
| Q23 | Initial single-platform scope, later revised. | `SUPERSEDED_BY_LATER_QUESTION` | Candidate: Q57 governs; LC-P3-05, W28. |
| Q24 | Separate interaction layer and local runtime. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-05, LC-P3-07. |
| Q25 | Initial fixed team model, later revised. | `SUPERSEDED_BY_LATER_QUESTION` | Candidate: Q54 governs; LC-P3-04, W12, W13. |
| Q26 | Initial role library invoked by task. | `CONFIRMED` | Candidate: LC-P3-04, W12, W13. |
| Q27 | One default model, advanced per-agent override later. | `CONFIRMED` | Candidate: LC-P3-06, W16. |
| Q28 | Unified workspace for projects, tasks and files. | `CONFIRMED` | Candidate: LC-P3-01, LC-P3-04, LC-P3-05, W16, W17, W28. |
| Q29 | Personalised research home page. | `CONFIRMED` | Candidate: W16, W17, W28. |
| Q30 | One client for personal and group modes. | `CONFIRMED` | Candidate: LC-P3-05, W14, W29. |
| Q31 | Shared client across deployment modes. | `CONFIRMED` | Candidate: LC-P3-05, LC-P3-06, W11, W12, W29. |
| Q32 | Unified identity with flexible authentication. | `CONFIRMED` | Candidate: W10, W11, W29. |
| Q33 | User-selected project sync scope. | `CONFIRMED` | Candidate: W11, W12, W29. |
| Q34 | Hybrid sync with offline queue and conflict handling. | `CONFIRMED` | Candidate: W11, W12, W29. |
| Q35 | Sensitivity-tiered storage, transfer and model access. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-06, W11, W12. |
| Q36 | Tiered model data authorisation and user control. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-06; later confirmation recorded. |
| Q37 | Layered credential, quota and billing modes. | `CONFIRMED` | Candidate: LC-P3-06, W10, W29. |
| Q38 | Hybrid model routing by deployment and authorisation. | `CONFIRMED` | Candidate: LC-P3-06, W11, W29. |
| Q39 | Risk-tiered execution isolation. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-05, LC-P3-07, W10, W11, W12. |
| Q40 | Preserve originals, diff and roll back working copies. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-03, LC-P3-04, LC-P3-07. |
| Q41 | Durable tasks with pause, cancel and recovery. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-05, LC-P3-07. |
| Q42 | Layered core, skills, connector and plugin extension. | `CONFIRMED` | Candidate: LC-P3-05, LC-P3-07, W10, W11, W16, W17, W19. |
| Q43 | Projects own materials, tasks, permissions and knowledge. | `CONFIRMED` | Candidate: LC-P3-03, W13, W14. |
| Q44 | Task-scoped retrieval with permission and provenance. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-04, LC-P3-06. |
| Q45 | Evidence-linked conclusions with uncertainty recorded. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, W22, W23. |
| Q46 | Separate file-delivery and research-quality gates. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, G3. |
| Q47 | Continuous refinement of guidance experience from reviewed cases. | `CONFIRMED` | Candidate: W15, W18, W21; later confirmation recorded. |
| Q48 | Scoped review, publication and withdrawal of experience. | `CONFIRMED` | Candidate: W15, W18, W21. |
| Q49 | Evolution archive links drafts, responses and outcomes. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-04, W22, W23. |
| Q50 | Retrieve applicable cases with conditions attached. | `CONFIRMED` | Candidate: LC-P3-04, W15, W18, W21. |
| Q51 | Multi-dimensional guidance-quality evaluation. | `CONFIRMED` | Candidate: LC-P3-08, W21, W27, G4. |
| Q52 | Staged experience release with version and rollback. | `CONFIRMED` | Candidate: W15, W18, W21. |
| Q53 | Arbitrate conflicts by evidence and scope. | `CONFIRMED` | Candidate: W15, W18, W21. |
| Q54 | Role library plus task-based team formation. | `CONFIRMED` | Candidate: LC-P3-04, W12, W13; later decision. |
| Q55 | Evidence review for agent disagreement, human escalation. | `CONFIRMED` | Candidate: LC-P3-04, W12, W13. |
| Q56 | Layered plan, progress, evidence and takeover views. | `CONFIRMED` | Candidate: LC-P3-01, LC-P3-04, LC-P3-05, LC-P3-07. |
| Q57 | Desktop-first launch with portable core contracts. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-05, W28; later decision. |
| Q58 | Deliver one complete workflow before breadth. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, G2, G3, G4. |
| Q59 | First workflow starts from a commented draft. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-03, LC-P3-04, LC-P3-08; later confirmation recorded. |
| Q60 | Locate comments, edit a copy, keep two DOCX outputs. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-03, LC-P3-04; a sample DOCX is the neutral fixture. |
| Q61 | Convert evidence gaps into explicit pending tasks. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, G3. |
| Q62 | Risk-tiered approval for methods, data and conclusions. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-04, G2. |
| Q63 | Workflow application plus professional DOCX editing. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-04, LC-P3-05, LC-P3-08. |
| Q64 | Role-based handoff of tasks, versions and feedback. | `CONFIRMED` | Candidate: LC-P3-08, W14, W15, W18. |
| Q65 | Combine file versions, comments and live collaboration. | `CONFIRMED` | Candidate: LC-P3-03, W11, W12, W14, W29. |
| Q66 | Local execution, shared storage, light cloud coordination. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-05, LC-P3-06, W11, W12, W29. |
| Q67 | Secure connection choices by network condition. | `CONFIRMED` | Candidate: W11, W12, W29. |
| Q68 | Layered protection for local, transit and shared data. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-06, W11, W12. |
| Q69 | Model access follows data sensitivity and least privilege. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-06. |
| Q70 | Dynamic model routing by capability and availability. | `CONFIRMED` | Candidate: LC-P3-06, W16, W29. |
| Q71 | Credential, quota and cost governance. | `CONFIRMED` | Candidate: LC-P3-06, W10, W29. |
| Q72 | Offline local work, cloud work resumes on reconnect. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-07, W11, W12. |
| Q73 | Risk-isolated local code, file and tool actions. | `CONFIRMED` | Candidate: LC-P3-03, LC-P3-05, LC-P3-07, W10, W11, W12. |
| Q74 | Unified tool registry across native and external capabilities. | `CONFIRMED` | Candidate: LC-P3-05, LC-P3-07, W10, W11, W12, W14, W16, W17, W19; later confirmation recorded. |
| Q75 | Govern third-party extensions by trust and isolation. | `CONFIRMED` | Candidate: LC-P3-07, W10, W11, W16, W17, W19. |
| Q76 | Self-service agent creation and cultivation. | `CONFIRMED` | Owner ruling 2026-11-07 (see `LC-P3-00`): the recorded recommendation is adopted as the decision. |
| Q77 | Memory-layer definition. | `ORIGINAL_MISSING` + `UNRESOLVED` | No stem and no options survive — the interview jumps 76 to 78; the five knowledge tiers are recoverable from Q78's answer, the per-tier boundaries, write rules and lifecycle are not. Trigger: before a memory interface is frozen, as a design task, not a reconstruction. |
| Q78 | Arbitrate knowledge by evidence, scope and age. | `CONFIRMED` | Candidate: W13, W15, W18, W19, W21. |
| Q79 | Separate evidence completeness from scientific correctness. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, W21, W22. |
| Q80 | Bulk historical import preserves originals and reviewable links. | `CONFIRMED` | Candidate: LC-P3-02, W13, W15, W18, W19. |
| Q81 | Separate paper submission from learning authorisation. | `CONFIRMED` | Owner ruling 2026-11-07: the recorded recommendation is adopted; the fresher confirmation segment arrived cut off mid-sentence and the material stream has ended, so the adoption governs unless the owner restates. |
| Q82 | Original question and conclusion unavailable. | `ORIGINAL_MISSING` + `UNRESOLVED` | Nothing survives — no stem, no options, no conclusion; the reverse-infer route cannot reach this row. Trigger: before a later requirements baseline is frozen; only an owner statement fills it. |
| Q83 | Attribution, licensing and contribution rights for shared knowledge. | `CONFIRMED` | Candidate: W20, W25. |
| Q84 | Tiered quality governance for shared knowledge. | `CONFIRMED` | Candidate: W20, W25. |
| Q85 | Show source, scope, evidence and uncertainty. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, W20, W25. |
| Q86 | Literature capture, citation and verification. | `CONFIRMED` | Owner ruling 2026-11-07: recommendation adopted, and a fresh confirmation segment arrived the same day — Option D, a dedicated literature centre with lifecycle management; authenticity checks rest on verifiable publication evidence. |
| Q87 | Full-text acquisition strategy across legitimate channels. | `CONFIRMED` | The original question arrived with the owner's 2026-11-07 segment — multi-channel retrieval, no paywall or licence circumvention, and metadata/abstract/full text kept as distinct tiers; Option D confirmed. |
| Q88 | From single-item analysis to domain synthesis. | `CONFIRMED` | Candidate: W22, W23, W24, W25, W26, W27. |
| Q89 | Track hypothesis, plan, execution and verification states. | `CONFIRMED` | Candidate: W22, W23, W24, W25, W26, W27. |
| Q90 | Staged instrument integration after data standardisation. | `CONFIRMED` | Candidate: W22, W23, W24, W25, W26, W27. |
| Q91 | Layered research data with version and lineage. | `CONFIRMED` | Candidate: LC-P3-02, LC-P3-03, W22, W23, W24, W25. |
| Q92 | Local-first analysis workbench with notebooks and visual tools. | `CONFIRMED` | Candidate: W22, W23, W24, W25, W26, W27. |
| Q93 | Layered checks with independent recomputation of key results. | `CONFIRMED` | Candidate: LC-P3-04, LC-P3-08, W22, W23, W24, W25, W26, W27. |
| Q94 | Reproducible chart creation and editing. | `CONFIRMED` | Candidate: W22, W23, W24, W25, W26, W27. |
| Q95 | Editable presentation output linked to real artifacts. | `CONFIRMED` | Candidate: W22, W23, W24, W25, W26, W27. |
| Q96 | Project-centred workspace with per-project isolation and authorised sharing. | `CONFIRMED` | Option D; the confirmation segment never arrived in the material, and the owner's ruling of 2026-11-07 closes this row by reverse-inference from the preserved stem and options. The formal name and detailed design expand at the workspace trigger. |

## Source and gaps

Q1-Q96 are traced from an external Word document. The rows above are short English decision topics, not question-by-question copies of the original text; no question text, options, long scenarios, examples, personal names or unpublished material content are reproduced. The related PDF material and the Chinese working drafts also stay outside the public repository.

The seven gaps recorded by the first draft — Q76, Q77, Q81, Q82, Q86, Q87 and Q96 — were ruled by the owner's dialogs of 2026-11-07, and the rulings are in [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md): five rows closed (recommendations adopted as decisions, owner segments received, and the workspace row by the owner's reverse-infer ruling from preserved stems and options); Q77 and Q82 remain open, and the reverse-infer route does not reach them because neither has preserved options. No work package is inferred from a missing original question; open rows remain triggers for a decision, not approval to build.
