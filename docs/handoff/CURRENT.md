# LabCairn — Current handoff

**Date:** 2026-10-15 (updated after the second project-lead review of PR #2)  
**Current `main`:** `9f9c4f0` — the commit this handoff describes. Anything newer is work in progress on a branch; check `git log origin/main` before trusting a higher SHA.  
**G0:** LC-P1-00 PASS WITH NOTES; subject SHA `623e3ca31caba327d2f8b1af40ab67c35c7a61d3` (review subject, not the current tip).  
**Review:** [LC-P1-00 report](../acceptance/LC-P1-00-review-623e3ca.md).  
**Current authorized work order:** G1 — LC-P1-02, LC-P1-03 and LC-P1-04 are **implemented on `feat/g1-trusted-core` and awaiting acceptance**; see [G1 evidence](../acceptance/G1-evidence.md). **G1 cannot close** until LC-P1-03's real-provider smoke runs, which needs the project owner's spending authorisation and a credential issued for that purpose. LC-P1-05 has **not** started.
**Binding decisions:** [LC-P1-01 amendments](../plans/LC-P1-01-approved-amendments.md).  
**PR #1 re-review:** [Independent technical re-review](../acceptance/PR-1-independent-review.md) — C-1, C-2, R-01 and R-02 were reproduced from primary evidence rather than accepted on assertion; all four confirmed. Two further script defects (R-05) were reproduced and fixed. Conflicting instructions in `UPSTREAM_REFERENCES.md`, `PHASE_1_WORKORDERS.md`, `LC-P1-01-task-breakdown.md`, `ADR-0002` and `README.md` were synchronized.

Next: **do not rebuild G1.** LC-P1-02/03/04 are implemented and awaiting acceptance. The only thing standing between them and a G1 close is the real-provider smoke, which needs the project owner's spending authorisation and a credential issued for that purpose — the flow is `pydantic_models.smoke_test()` and removing the skip is the whole change. After acceptance, LC-P1-05 owns persistence; ADR-0006's outbound-consent bridge belongs there.

**Merge authority.** From this point the implementing agent merges its own PRs after both the parent and a non-implementing reviewer have signed off and all required CI checks pass. Merge authorisation comes from the project plan, not from an external auditor.

Paused pending a project-lead decision, because they are not the implementing agent's to make: expanding data access scope, write permission to original material, unapproved outbound transmission, any model-generated code execution, major architecture change, and the unresolved PyMuPDF licence obligation before LC-P1-08.

Notes carried forward from the review, none blocking: the Gitleaks allowlist guard is textual and has a multi-line/nested TOML weakness (structural parsing is a tracked follow-up); the README capability-claim detector has known holes and is a floor, not a truth-checker; no real-browser or Windows-app smoke exists, and the dedicated packaging job is Linux-only. Copyright ownership is unresolved and there is still **no `LICENSE` file**; PyMuPDF's AGPL/commercial duality gates LC-P1-08.

Open items carried forward: copyright ownership is unresolved and there is still **no `LICENSE` file**, so the project describes itself as in development with open-source licensing pending; PyMuPDF's AGPL/commercial duality is unresolved and gates LC-P1-08. The README overclaim detector has known holes and is a floor, not a guarantee.
