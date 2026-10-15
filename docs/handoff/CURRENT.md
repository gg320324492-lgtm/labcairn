# LabCairn — Current handoff

**Date:** 2026-10-15 (updated after the second project-lead review of PR #2)  
**Current `main`:** `89c16d4` — the commit this handoff describes. Anything newer is work in progress on a branch; check `git log origin/main` before trusting a higher SHA.  
**G0:** LC-P1-00 PASS WITH NOTES; subject SHA `623e3ca31caba327d2f8b1af40ab67c35c7a61d3` (review subject, not the current tip).  
**Review:** [LC-P1-00 report](../acceptance/LC-P1-00-review-623e3ca.md).  
**Current authorized work order:** LC-P1-01 is **accepted and merged** (`PASS WITH NOTES` at `c23ef775`, merged `89c16d4`). **LC-P1-02 (contracts) is the next work order and has NOT STARTED.** G1 stays IN PROGRESS — it spans LC-P1-02, 03 and 04 as well.
**Binding decisions:** [LC-P1-01 amendments](../plans/LC-P1-01-approved-amendments.md).  
**PR #1 re-review:** [Independent technical re-review](../acceptance/PR-1-independent-review.md) — C-1, C-2, R-01 and R-02 were reproduced from primary evidence rather than accepted on assertion; all four confirmed. Two further script defects (R-05) were reproduced and fixed. Conflicting instructions in `UPSTREAM_REFERENCES.md`, `PHASE_1_WORKORDERS.md`, `LC-P1-01-task-breakdown.md`, `ADR-0002` and `README.md` were synchronized.

Next: **LC-P1-01 is closed.** Do not rebuild it. Start LC-P1-02: versioned contracts for Task, Run, Stage, Operation, Approval, Evidence and the event envelopes — JSON round-trip, schema-version compatibility and malformed-input tests. Freeze those contracts before LC-P1-03 and LC-P1-04 branch in parallel.

**Merge authority.** From this point the implementing agent merges its own PRs after both the parent and a non-implementing reviewer have signed off and all required CI checks pass. Merge authorisation comes from the project plan, not from an external auditor.

Paused pending a project-lead decision, because they are not the implementing agent's to make: expanding data access scope, write permission to original material, unapproved outbound transmission, any model-generated code execution, major architecture change, and the unresolved PyMuPDF licence obligation before LC-P1-08.

Notes carried forward from the review, none blocking: the Gitleaks allowlist guard is textual and has a multi-line/nested TOML weakness (structural parsing is a tracked follow-up); the README capability-claim detector has known holes and is a floor, not a truth-checker; no real-browser or Windows-app smoke exists, and the dedicated packaging job is Linux-only. Copyright ownership is unresolved and there is still **no `LICENSE` file**; PyMuPDF's AGPL/commercial duality gates LC-P1-08.

Open items carried forward: copyright ownership is unresolved and there is still **no `LICENSE` file**, so the project describes itself as in development with open-source licensing pending; PyMuPDF's AGPL/commercial duality is unresolved and gates LC-P1-08. The README overclaim detector has known holes and is a floor, not a guarantee.
