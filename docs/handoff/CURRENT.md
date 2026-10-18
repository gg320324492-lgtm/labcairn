# LabCairn — Current handoff

**Date:** 2026-10-18
**Current `main`:** `98b5ea5`, the merge of PR #31 (LC-P1-08's acceptance review and the eight defects it found). LC-P1-08's acceptance review is on `fix/lc-p1-08-acceptance-findings` and is not yet merged. The merges since the previous refresh: #25 (XLSX), #26 (single-column PDF), #27 (ADR-0010 ratification), #28 (the workspace walk), #29 (the permission-boundary fix and [ADR-0011](../adr/ADR-0011-canonical-policy-matching.md)), #30 (ADR-0011 ratification).

**This file rots on every merge and no test can catch it.** `tests/test_status_consistency.py` checks that the gate table agrees with the plan, that every status is from the declared vocabulary, that a row claiming progress cites evidence, and that relative links resolve — but "how far along is the work" is a semantic judgement, not a parseable fact. This file was **six merges stale** when it was last checked: it named PR #24 as current and claimed no material parsing existed, which stopped being true at #25. Refresh it in the PR that reports the change, and check `git log origin/main` rather than trusting it.

## Gates

| Gate | Status |
|---|---|
| G0 | **closed** — LC-P1-00 PASS WITH NOTES, subject `623e3ca` |
| G1 | **closed** — LC-P1-01 PASS WITH NOTES, LC-P1-02 PASS, LC-P1-04 PASS, LC-P1-03 PASS WITH NOTES |
| **G2** | **closed** — LC-P1-05/06/07 all PASS WITH NOTES. [Acceptance](../acceptance/G2-acceptance.md) · [narrative record](../acceptance/G2-evidence.md) |
| G3 | **in progress** — LC-P1-08 **PASS WITH NOTES** by owner decision; LC-P1-09 [decomposed](../plans/LC-P1-09-task-breakdown.md), not implemented; LC-P1-10 not started |

## What exists now

The engineering floor from G2: versioned contracts, provider adapters with fail-closed budgets, workspace permissions, a SQLite task store with transactional events, crash recovery that enters UNCERTAIN rather than guessing, and the `research-report` Skill contract.

And, from LC-P1-08: **material ingestion works end to end.** Text, Markdown, CSV, XLSX and PDF adapters produce text units with locators — page, line, row+header, sheet+cell — which a workspace walk reads through `SourceMaterial` and stores as `sources` rows plus content-addressed `source_texts`, with hashed bytes and workspace-relative paths. Unreadable material is separated from empty material and from readable material, and neither unreadable state is citable.

Both exit demonstrations run green:

```bash
uv run python examples/g2_exit_demo.py      # persist, crash, restart, resume — 14 checks
uv run python examples/g2_uncertain_demo.py # the uncertain path end to end — 18 checks
```

## What does not exist yet

**No research capability.** Retrieval, the evidence ledger, analysis, plots, claims and citations are all still unbuilt — the ledger's *contracts* exist and are frozen, but C1, C2 and C3 raise `CiteSupportNotImplementedError` and `SourceIndex` is a Protocol nobody implements. No CLI, no server, no web UI, and no model call that leaves the machine.

## Next: finish G3

LC-P1-08 (material parsing and locators) → LC-P1-09 (FTS5 retrieval and the evidence ledger) → LC-P1-10 (bounded statistics and deterministic plots).

**LC-P1-08 was accepted with notes by owner decision, not by independent review.** Its acceptance review is [written up](../acceptance/LC-P1-08-acceptance.md) and records eight defects found and fixed — most seriously, a two-column PDF storing sentences the author never wrote and marking them citable. The review and the fixes are the same party, so the board's rule is not discharged; the owner decided on 2026-10-18 to proceed without it, and the board records that as a decision rather than as a review.

**LC-P1-09 is decomposed and ready.** [Task breakdown](../plans/LC-P1-09-task-breakdown.md): ten subtasks with a file-ownership map for parallel work, and ADR-0004 Contract 4's twelve conditions each mapped to the subtask and test that carries it. Nothing is implemented.

**Its PDF library question is settled.** [ADR-0008](../adr/ADR-0008-pdf-ingestion-library.md) puts it on pdfplumber + pdfminer.six, both MIT, rather than PyMuPDF, whose AGPL branch would have constrained LabCairn's own MIT release. Nothing needed undoing.

**The two-column PDF question is also settled, as a refusal.** Reading order is not reconstructed. A page that reads as two columns is refused and disclosed rather than extracted, because splicing two columns stores sentences the author never wrote — that defect was real, reproduced, and is the reason the refusal exists. Rotated text is still not detected, and there is no two-column paper in the repository to test detection against.

## Carried limitations, none blocking

- **LC-P1-08:** rotated PDF text is **not detected**. A rotated page would
  extract in the wrong order and nothing would record it. ADR-0008 constraint 7
  is unmet, and this is the honest reason the two-column work stopped at
  refusal rather than proceeding to reconstruction.
- **LC-P1-08:** the two-column detector is bracketed against single-column
  fixtures, not calibrated against two-column ones — there is no two-column
  paper in the repository to calibrate against. Its threshold is defensible
  because it refuses loudly, not because it is known to catch every layout.
- **LC-P1-08:** anchors are validated only in their **positive** direction. No
  code in `src/` consumes a locator and returns content, so nothing yet shows
  that a wrong locator misses. That becomes checkable in LC-P1-09 with C1–C3.
- **LC-P1-08:** `UNPARSEABLE` is a mixed bucket — a container that would not
  open, and a page deliberately not read. Both are honestly "not citable, here
  is why", but only the disclosure separates them.
- **G1:** `ApprovalLedger.consume()` does not resolve the capability against the registry. Only `policy.evaluate()` turns an unknown id into DENY, and nothing enforces that a caller evaluates first. The ordering constraint belongs in an ADR.
- **G1:** path-guard tests ran on Windows only. POSIX ADS and case semantics are unverified.
- **G1:** ADR-0006's outbound-consent bridge is not built. Both modules exist.
- **G1:** structured-output capability is unmeasured — both probes fail in pydantic-ai's client layer before a request is sent.
- **G2:** `ArtifactLedger` is in memory. LC-P1-07's ledger does not survive a restart; the store does.
- **Cross-gate:** the Gitleaks allowlist guard is textual and has a multi-line/nested TOML weakness.
- **Cross-gate:** the README capability-claim detector has known holes. It is a floor, not a truth-checker.
- **Cross-gate:** copyright ownership is unresolved and there is still **no `LICENSE` file**. The project describes itself as in development with open-source licensing pending.

## Merge authority

The implementing agent merges its own PRs after both the parent and a non-implementing reviewer have signed off and all required CI checks pass. Merge authorisation comes from the project plan, not from an external auditor.

## Escalate to the project lead

Expanding data access scope, write permission to original material, unapproved outbound transmission, any model-generated code execution, and major architecture change. The PyMuPDF licence obligation is now **resolved** (ADR-0008) and no longer needs escalating; **copyright ownership remains unresolved** and still does.
