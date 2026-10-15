# LC-P1-00 — Independent review

**Verdict:** PASS WITH NOTES — G0 closed; LC-P1-01 authorized.  
**Reviewed:** 2026-10-15  
**Subject commit:** [623e3ca31caba327d2f8b1af40ab67c35c7a61d3](https://github.com/gg320324492-lgtm/labcairn/commit/623e3ca31caba327d2f8b1af40ab67c35c7a61d3)

## Evidence and scope

Inspected all 14 tracked files, including source reference catalog, three architecture ADRs, local verification diary and the LC-P1-01 breakdown. Independently resolved all five pinned upstream commit SHAs on GitHub and checked selected Deep Agents, PaperQA2 and license implementation paths. This review **did not** run the user's Windows local scripts, inspect their private local clones, or test a nonexistent product build.

| Check | Finding |
|---|---|
| Separate public repo, no tracked upstream code/submodules | PASS |
| Five upstream pin SHAs, function-level comparisons | PASS |
| ADR analysis of alternatives and tests | PASS WITH NOTES |
| Licensing | PASS WITH NOTES — `paper-qa-pymupdf` subpackage AGPL-3.0; PDF dependency choice unresolved |
| Local clone manifests and scripted results | Documentation reviewed; not independently reproduced |
| External build without clones | DEFERRED to LC-P1-01 |
| Phase 1 implementation/reuse dossier | DEFERRED to LC-P1-14 |

Independent corrections: Deep Agents' default middleware no longer includes `TodoListMiddleware` at its pinned SHA, but this **does not** mean the framework cannot support opt-in planning. PaperQA2 `PQASession.used_contexts` checks citation-ID presence, not semantic sentence support. All five pinned commit objects resolved via GitHub at review time, contrary to a statement that they exist only locally; future remote retention is not guaranteed.

## Findings and follow-up

- **R-01 / blocking before schema implementation:** ADR-0003 conflates SQLite global `AUTOINCREMENT` with per-Task gapless `seq`. Use a separate database row PK and `UNIQUE(task_id,seq)`; allocate from `tasks.last_event_seq` inside the same `BEGIN IMMEDIATE` transaction as event and state updates. Test committed events under concurrent writes and rollback.
- **R-02 / blocking before schema implementation:** `task_created` and `task_revised` do not necessarily belong to a Run. Allow `run_id = NULL` on Task-level events; require Run IDs (and corresponding stage/operation IDs) on lower-level events; validate by event type.
- **R-03:** Resolve C-1/C-2: required PR checks cannot be skipped by `pull_request.paths-ignore`; use correct explicit Hatchling packaging instead of an invalid setuptools leaf-package interpretation.
- **R-04:** PyMuPDF AGPL/commercial licensing remains a dependency decision, not automatically compatible with a future MIT release.
- **R-05:** Test `checkout_upstreams.py` for non-dict snapshot JSON (currently can raise an unintended AttributeError) and for checkout paths inside an ancestor Git repository (`rev-parse HEAD` alone does not prove checkout root).
- **R-06:** Update stale G0 checklist and README license language; LC-P1-01's T01 must recognize the initial commit already exists.
- **R-07:** Do not broadly allowlist tracked reference-looking folders in Gitleaks; a mistaken `git add -f` must be visible to both leak tests and secret scans.

**Final decision:** G0 = PASS WITH NOTES. Work may start on LC-P1-01 after adopting [approved amendments](../plans/LC-P1-01-approved-amendments.md). No runtime, CI, license grant or scientific validation has been certified by this review.
