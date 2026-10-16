# LabCairn — Current handoff

**Date:** 2026-10-15 (updated after the second project-lead review of PR #2)  
**Current `main`:** `9f9c4f0` — the commit this handoff describes. Anything newer is work in progress on a branch; check `git log origin/main` before trusting a higher SHA.  
**G0:** LC-P1-00 PASS WITH NOTES; subject SHA `623e3ca31caba327d2f8b1af40ab67c35c7a61d3` (review subject, not the current tip).  
**Review:** [LC-P1-00 report](../acceptance/LC-P1-00-review-623e3ca.md).  
**Current authorized work order:** **G1 is closed** (project lead's decision, recorded in the status board). **LC-P1-05** — SQLite task store and transactional events — is next and has started. G1's three accepted limitations are listed in the status board rather than dropped.
**Binding decisions:** [LC-P1-01 amendments](../plans/LC-P1-01-approved-amendments.md).  
**PR #1 re-review:** [Independent technical re-review](../acceptance/PR-1-independent-review.md) — C-1, C-2, R-01 and R-02 were reproduced from primary evidence rather than accepted on assertion; all four confirmed. Two further script defects (R-05) were reproduced and fixed. Conflicting instructions in `UPSTREAM_REFERENCES.md`, `PHASE_1_WORKORDERS.md`, `LC-P1-01-task-breakdown.md`, `ADR-0002` and `README.md` were synchronized.

Next: **LC-P1-05.** Alembic migrations, the eight tables, per-Task gapless `seq` allocated inside the transaction, and event/state committed together per ADR-0003 C3. ADR-0006's outbound-consent bridge belongs here too — it is the first place a model capability and a permitted `CapabilityId` have to be reconciled.

**Merge authority.** From this point the implementing agent merges its own PRs after both the parent and a non-implementing reviewer have signed off and all required CI checks pass. Merge authorisation comes from the project plan, not from an external auditor.

Paused pending a project-lead decision, because they are not the implementing agent's to make: expanding data access scope, write permission to original material, unapproved outbound transmission, any model-generated code execution, major architecture change, and the unresolved PyMuPDF licence obligation before LC-P1-08.

Notes carried forward from the review, none blocking: the Gitleaks allowlist guard is textual and has a multi-line/nested TOML weakness (structural parsing is a tracked follow-up); the README capability-claim detector has known holes and is a floor, not a truth-checker; no real-browser or Windows-app smoke exists, and the dedicated packaging job is Linux-only. Copyright ownership is unresolved and there is still **no `LICENSE` file**; PyMuPDF's AGPL/commercial duality gates LC-P1-08.

Open items carried forward: copyright ownership is unresolved and there is still **no `LICENSE` file**, so the project describes itself as in development with open-source licensing pending; PyMuPDF's AGPL/commercial duality is unresolved and gates LC-P1-08. The README overclaim detector has known holes and is a floor, not a guarantee.
