# LabCairn — Current handoff

**Date:** 2026-10-17
**Current `main`:** `310bdd0` (merge of PR #16, the G2 acceptance and its independent cross-review). ADR-0008 sits on top of this and is not yet merged at the time of writing. **This line rots on every merge** — check `git log origin/main` rather than trusting it, and refresh it in the PR that reports the change.

## Gates

| Gate | Status |
|---|---|
| G0 | **closed** — LC-P1-00 PASS WITH NOTES, subject `623e3ca` |
| G1 | **closed** — LC-P1-01 PASS WITH NOTES, LC-P1-02 PASS, LC-P1-04 PASS, LC-P1-03 PASS WITH NOTES |
| **G2** | **closed** — LC-P1-05/06/07 all PASS WITH NOTES. [Acceptance](acceptance/G2-acceptance.md) · [narrative record](acceptance/G2-evidence.md) |
| G3 | **next** — LC-P1-08 material parsing, LC-P1-09 retrieval and evidence ledger, LC-P1-10 bounded analysis and plots |

## What exists now

The engineering floor: versioned contracts, provider adapters with fail-closed budgets, workspace permissions, a SQLite task store with transactional events, crash recovery that enters UNCERTAIN rather than guessing, and the `research-report` Skill contract.

Both exit demonstrations run green:

```bash
uv run python examples/g2_exit_demo.py      # persist, crash, restart, resume — 14 checks
uv run python examples/g2_uncertain_demo.py # the uncertain path end to end — 18 checks
```

## What does not exist yet

**No research capability.** No material parsing, no retrieval, no evidence ledger, no analysis, no plots. No CLI, no server, no web UI, and no model call that leaves the machine. G2 is a durable, recoverable floor, not a product.

## Next: G3

LC-P1-08 (material parsing and locators) → LC-P1-09 (FTS5 retrieval and the evidence ledger) → LC-P1-10 (bounded statistics and deterministic plots).

**LC-P1-08 is unblocked.** Its PDF library was PyMuPDF, which is AGPL/commercial dual-licensed — the AGPL branch would have constrained LabCairn's own future MIT release, and the commercial branch cannot be contracted while copyright ownership is unsettled. [ADR-0008](../adr/ADR-0008-pdf-ingestion-library.md) settles it on pdfplumber + pdfminer.six, both MIT. Nothing needed undoing: ADR-0004's locator contract was already independent of PyMuPDF, and no PDF dependency had been added.

## Carried limitations, none blocking

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
