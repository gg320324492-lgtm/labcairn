# LabCairn Phase 1 Evaluation Protocol

**Version:** LC-P1-v1.1  
**Updated:** 2026-10-15  
**Status:** Test protocol definition; no results have been measured yet.

## Fixed public fixtures

Use permissively licensed or synthetic, clearly labeled materials. Minimum 3 tasks across distinct research genres (e.g. physical sciences, biomedical-style tabular measurements without real patient data, computational experiments), each with source PDFs/text, tabular data, grounded questions, and expected artifact checks. Fixtures must have actual source locators, hashes and answer keys; do not use generated outputs as their own oracle.

## Mandatory automated gates

1. Unit: model/provider-independent typed contracts, state transitions, permission resolution, path traversal/symlinks, dataset locators, numerical extraction and report serialization.
2. Integration: SQLite migrations, transactional event append, restart recovery, approvals, artifact hashes, local API auth and provider redaction.
3. Negative: fabricated citation, missing material, conflicting numeric values/units, insufficient evidence, outdated checkpoint, simulated crash between file change and operation confirmation, untrusted document instructions.
4. E2E: fresh install + CLI task, local Web task, resume and revise, Markdown and DOCX/PDF export, source click-through.
5. Real-model smoke: at least one real supported provider under declared model/version/parameters; results and costs documented. Mock-only success is insufficient.

## Metrics to report with denominators and failure cases

- End-to-end task success (successful verified deliveries / attempted tasks).
- Evidence locator validity and citation support precision (human-checked sample).
- Numeric-cell extraction exactness and unit consistency.
- Unsupported-claim detection and appropriate abstention.
- Revision consistency; no stale figure/caption/reference retained after source change.
- Recovery correctness / duplicate side effects across fault-injection runs.
- Latency, model usage/cost with model name, dataset revision and seeds where meaningful.

Results are benchmarks only when measured on immutable fixture/version labels. Do not claim superiority over PaperQA2/PaperSpine/others without like-for-like matched-task baselines, verified capabilities, and documented confidence intervals or limitations.

## Phase 1 blockers

- New user cannot complete a task from a clean environment following README.
- Any unauthorized file write/escape or unconsented private-network disclosure.
- Fake citation presented as verified or unsupported numerical fact presented as measured.
- A crash silently repeats unknown file side effects.
- Report claims a verified scientific result based solely on schema or rendering checks.
- Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance.
