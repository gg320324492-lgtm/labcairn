# LabCairn — Current handoff

**Date:** 2026-10-19
**Current `main`:** the merge of PR #39 (LC-P1-09 T05, C1), `c0f9c1e`. This PR (#40) lands T06 and T07 — C2 and C3 — so once it merges the head advances again; the merges since the previous refresh are #32 (LC-P1-09's task breakdown), #33 (T01, the evidence tables), #34 (T02, normalisation), #35 (the ground-truth query set), #36 (T03, the FTS5 index), #37 (T04, building the index from ingestion), #38 (T05a, the anchor registry) and #39 (T05, C1).

**This file rots on every merge and no test can catch it.** `tests/test_status_consistency.py` checks that the gate table agrees with the plan, that every status is from the declared vocabulary, that a row claiming progress cites evidence, and that relative links resolve — but "how far along is the work" is a semantic judgement, not a parseable fact. This file was **six merges stale** when it was last checked: it named PR #24 as current and claimed no material parsing existed, which stopped being true at #25. It was then stale again at #32, and the claim it made — "Nothing is implemented" for LC-P1-09 — stopped being true at #33. Refresh it in the PR that reports the change, and check `git log origin/main` rather than trusting it.

## Gates

| Gate | Status |
|---|---|
| G0 | **closed** — LC-P1-00 PASS WITH NOTES, subject `623e3ca` |
| G1 | **closed** — LC-P1-01 PASS WITH NOTES, LC-P1-02 PASS, LC-P1-04 PASS, LC-P1-03 PASS WITH NOTES |
| **G2** | **closed** — LC-P1-05/06/07 all PASS WITH NOTES. [Acceptance](../acceptance/G2-acceptance.md) · [narrative record](../acceptance/G2-evidence.md) |
| G3 | **in progress** — LC-P1-08 **PASS WITH NOTES** by owner decision; LC-P1-09 [implemented and reviewed](../acceptance/LC-P1-09-acceptance.md) — **PASS WITH NOTES**: all ten subtasks merged, three review findings fixed, and two clauses of the acceptance not discharged (the *fabricated DOI* half, and provenance through report generation, which is LC-P1-11's); LC-P1-10 not started |

## What exists now

The engineering floor from G2: versioned contracts, provider adapters with fail-closed budgets, workspace permissions, a SQLite task store with transactional events, crash recovery that enters UNCERTAIN rather than guessing, and the `research-report` Skill contract.

And, from LC-P1-08: **material ingestion works end to end.** Text, Markdown, CSV, XLSX and PDF adapters produce text units with locators — page, line, row+header, sheet+cell — which a workspace walk reads through `SourceMaterial` and stores as `sources` rows plus content-addressed `source_texts`, with hashed bytes and workspace-relative paths. Unreadable material is separated from empty material and from readable material, and neither unreadable state is citable.

And, from LC-P1-09 so far: **the ledger has a store, an index and one working check.**

- Revision 0005 creates `evidence_records`, `evidence_anchors`, `verification_records` and the `evidence_fts` FTS5 table; 0006 rebuilds that table on a **trigram** tokenizer, and 0007 adds `source_anchors`, the anchor registry.
- Normalisation is an index-side copy with a declared profile and an `alters_letters` flag, so a comparison can report how lossy it was (T02).
- Retrieval works over the real papers: fifteen ground-truth queries, eleven that must find the right pages and four that must find nothing, validated against the PDFs before any index existed (T03).
- The index is built from the store and reports what it excluded (T04).
- **All four cite-support checks answer.** `check_source_exists` resolves every cited anchor and
  compares three separate hashes (T05). `check_quotation_support` walks a ladder of four
  normalisation profiles and refuses to promote a lossy match to `pass` (T06).
  `check_numeric_consistency` re-reads the anchored cell and compares parsed values under a
  declared tolerance (T07). C4 returns `not_checked` and always will.
- **The ledger persists records through a state machine** (T08). `advance` and
  `attest` are the only ways a status changes, and each refusal names the
  Contract 2 rule it refused. A `verified_by_rule` record's passing entry must
  name a checker id in the rule catalog -- the one rule the model cannot
  enforce, because it accepts any id, and a human attestation is logged by a
  human's id.
- **The evidence gate refuses** (T09). It re-runs the checks rather than reading
  their verdicts -- a record whose source has drifted is invalidated, not kept
  with a stale "pass" -- and it refuses as a whole: `citable` is empty when any
  record fails, because a partial list would invite a caller to cite the ones
  that survived. A conflict is handed over as data with two interchangeable
  sides, so the structure itself cannot express a winner.

Both exit demonstrations run green:

```bash
uv run python examples/g2_exit_demo.py      # persist, crash, restart, resume — 14 checks
uv run python examples/g2_uncertain_demo.py # the uncertain path end to end — 18 checks
```

## What does not exist yet

**No research capability yet.** There is no CLI, no server, no web UI, and no model call that
leaves the machine. All four cite-support checks now have bodies, and `IMPLEMENTED_CHECKS` is
every one of them — the set no longer distinguishes "implemented" from "not", and what still
separates them is that C4 can never return a pass.

Retrieval now answers the two-negative question (T10): a search that breaks is a `PROVIDER_FAILURE` and never a `no_hit`, and the boundary refuses to hand a caller an empty context. What is still unbuilt is everything around it — the analysis, the report renderer, and the model call the evidence would feed. And the gate is reachable from a ledger rather than from a report: nothing renders a `GateResult` yet, so "a report cites nothing when the gate refuses" is enforced at the gate and asserted at the record model, not observed in a rendered document. That demonstration is LC-P1-11's to make. The ledger's conflict rule covers numeric records about the same cell; the claim-side conflict ADR-0004 A5 also describes is not implemented, because the schema's own uniqueness constraint makes two claim records unable to collide.

## Next: finish G3

LC-P1-08 (material parsing and locators) → LC-P1-09 (FTS5 retrieval and the evidence ledger) → LC-P1-10 (bounded statistics and deterministic plots).

**LC-P1-08 was accepted with notes by owner decision, not by independent review.** Its acceptance review is [written up](../acceptance/LC-P1-08-acceptance.md) and records eight defects found and fixed — most seriously, a two-column PDF storing sentences the author never wrote and marking them citable. The review and the fixes are the same party, so the board's rule is not discharged; the owner decided on 2026-10-18 to proceed without it, and the board records that as a decision rather than as a review.

**LC-P1-09 is under way.** [Task breakdown](../plans/LC-P1-09-task-breakdown.md): ten subtasks with a file-ownership map for parallel work, and ADR-0004 Contract 4's twelve conditions each mapped to the subtask and test that carries each one. T01 (the tables), T02 (normalisation), the ground-truth set, T03 (the index and address resolution), T04 (building the index from ingestion) and T05a (the anchor registry) are merged. T05's C1 is in progress; T06, T07, T08, T09 and T10 are not started.

One thing worth knowing before reading the code: **`SourceIndex`'s members were never specified by ADR-0004.** The ADR requires C1 to "fail if an anchor id is unknown", but the Protocol it names takes no id — `locate` wants a whole anchor and `content_hash` a source id, and a record carries only `anchor_ids` as bare strings. Revision 0007 and `load_anchor` close that seam. It is recorded as an execution note at the head of ADR-0004, because it is the requirement's missing implementation rather than a change to the contract.

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
- **LC-P1-08, discharged by LC-P1-09:** anchors were validated only in their
  **positive** direction — no code consumed a locator and returned content, so
  nothing showed that a wrong locator misses. `locate_anchor` now does exactly
  that, and C1's tests assert both halves: a locator naming page 99 of a
  three-page paper fails, and the failure names that address and no other.
  What is *not* yet shown is the end-to-end version — that a report built from
  a record whose locator failed cites nothing — because there is no report
  renderer (LC-P1-11).
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
