# LC-P4-G0 — Phase 4 baseline freeze

**Ticket:** LC-P4-G0 (Phase 4 G0)
**Status:** `IN PROGRESS`
**Source plan:** [`PHASE_4-execution-plan.md`](PHASE_4-execution-plan.md) §5
(P4-G0 baseline freeze), opened after Phase 3's exit decision was signed
2026-11-22 (`PASS WITH NOTES`).

This ticket freezes Phase 3's close-out as Phase 4's input: every carried
item gets a Phase 4 owner, the Phase 3 board stops carrying stale wording,
the Phase 4 baseline version and Windows environment are named, and the
pilot's data model (task ↔ opinion ↔ version ↔ deliverable ↔ issue links)
is specified. **The repository carries no sample text** — the no-material
boundary from Phase 3 continues: raw material stays in the authorised
environment (`E:/trial-material/`), and this ticket's records carry
digests, counts, ids and paths only.

## 1. Work items

1. **Register the Phase 3 carry-over as Phase 4 inputs** — this file, §2.
   Each carried item names the Phase 4 work package that closes it and the
   closing condition restated in Phase 4 terms.
2. **Update the Phase 3 work-order board's top status** so historical
   wording does not travel into the Phase 4 handoff
   ([PHASE_3-work-orders.md](PHASE_3-work-orders.md)). Land one edit per
   stale statement, in the commit that carries this ticket's evidence.
3. **Freeze the Phase 4 baseline version and Windows environment** — §3.
4. **Name the pilot material** (authorised desensitised copy, digests,
   boundaries) — §4. Not the material itself; the pointer record.
5. **State the real-model service boundary** (provider, budget, timeouts,
   error and stop conditions) — §5.
6. **Specify the pilot data model's link fields** (task, opinion, version,
   deliverable, issue) — §6.

## 2. Phase 3 carry-over registered as Phase 4 inputs

From the signed exit decision
([LC-P3-08-exit-decision-2026-11-22.md](../acceptance/LC-P3-08-exit-decision-2026-11-22.md)
Field 5) and the trial record's limits list, each item below is carried
into Phase 4 with its closing owner:

| # | Carried item (Phase 3 record) | Phase 4 owner | Closing condition in Phase 4 terms |
|---|---|---|---|
| 1 | Strip-stage OOXML malformation — **FIXED** at `ce1f2f0…`; product `src/labcairn/editing/strip.py`, 7 witnesses (`tests/test_editing_strip.py`); closed | — (closed; regression-watched by the existing witnesses) | None — stays closed unless a witness fails |
| 2 | No apply/publish stage (rows 1/3/6 measured gaps) | **P4-CAP** (§7.1–7.3 of the plan) | The ten-step apply/publish loop runs end to end on the pilot paper; the four deliverables bind to one task, input version and output version; cancel/timeout/lock/interrupt/restart-recovery verified |
| 3 | Row-7 named gap — one real model (LC-P3-06 `BLOCKED`) | **P4-CAP** (§7.2) | One authorised real model generates suggestions on the desensitised sample under §5's budget/stop conditions, with retry and fallback; model suggestions stored separately from human approvals |
| 4 | First-launch supply gap — **closed for 0.0.2+** (adjudicated 2026-11-22) | — (closed) | None — the 0.0.2+ installer materialises a live `resources/shell-env.json`; regression-watched by the installer smoke |
| 5 | Row 5's class-coverage delta (six of seven refusal classes observed; trial-refusal record unfilled) | **P4-CAP** (§7.4 evidence checks) with the permission boundary owners | Each named attack class injected and refused at an openable address; the refusal record filled per class |
| 6 | Row 4's three-case research-quality shape absent (analysis loop emits no prose suggestions) | **P4-CAP** (§7.1 step 3) | The real-model loop produces the three named case statuses (prose-edit/quality) on the pilot paper |
| 7 | Distribution record not refilled for 0.0.2/0.0.3 | **P4-G0 item 3** (this ticket's §3) | This ticket's baseline record names the installer identity per version rhythm §10; the pilot's release notes carry install/run/rollback per version |
| 8 | T6 record's "the session" wording (review C-10 / C-B11 auditability note) | **P4-G0 item 2** | One clarifying sentence naming who/what drove the trial-day host opens, added to the trial record's carried-notes close-out |

Not carried (already closed before or at Phase 3 exit, listed so the next
reader does not re-open them): the killed-write temp-file limit,
`source_changed` on locked originals, the per-run stop-loss, drill-defect
D-07-01 (fixed for 0.0.2+), the `root_kinds={"source"}` seam (known limit,
re-stated in the trial record), and Phase 2's `real_model_smoke = NOT RUN`
(scope note in the exit decision's signature).

## 3. Phase 4 baseline version and Windows environment

Frozen at this ticket's commit:

- **Code baseline:** the Phase 3 exit commit lineage — `main` at the merge
  of PR #221 (`a8a822f…`), which carries the exit decision `15c7a18…`, the
  strip fix `ce1f2f0…` and the final sweep `cf26a4e…`.
- **Baseline installer lineage:** 0.0.3
  (`681607c7de0a2963016ff461e8999cef4fda369fa27b896475b70f6466874588`,
  354,088,228 B, built from `ce1f2f0…`; install / HKCU registration /
  `shell-env` materialisation / uninstall smoke passed 2026-11-22).
- **Reference hosts:** WPS Office 12.1.0.29690 and Microsoft Office 2019
  (16.0.17932.21140) on Windows 11 Pro (10.0.26300), machine
  `DESKTOP-BJJHSDF` — the dual-host pair every deliverable reopen is
  measured against.
- **Web/Python suite baseline:** 142 web workbench tests and the Phase 4
  Python target tests green at the baseline commit (per the plan's §2
  baseline statement, re-measured on this tree before each work package
  lands).
- **Distribution-record refill (carry-over item 7):** each Phase 4 version
  records version + source commit, installer sha256 + size, data/API
  compatibility, new capabilities, fixes, open limits and rollback, per
  plan §10. The 0.0.2/0.0.3 identities above are the first two entries.

## 4. Pilot material pointer (no material in the repository)

- One authorised real paper, desensitised copy, retaining annotations,
  revision marks and structure; names, affiliations and project numbers
  removed (plan §9.1).
- The Phase 3 trial's advisor-annotated working sample (sha256
  `a7a38132…`, 8,871,367 B, measured 2026-11-21/22 against the T1 supply
  receipt) is the standing candidate; the pilot's final material choice is
  the owner's, recorded in the pilot ticket when P4-PILOT opens.
- Boundary: raw files live only in `E:/trial-material/` (samples, stripped
  manuscripts, workspace, logs) and `E:/labcairn-local/p308-trial-run/`
  (records, installer, screenshots). The repository holds digests, counts,
  ids and paths — the same boundary the trial record states.

## 5. Real-model service boundary (fills the plan's pre-kickoff input)

- **Provider/model:** to be authorised by the owner before P4-CAP's
  real-model step runs; the authorisation record names provider, model id,
  purpose and scope, in the style of the LC-P3-06 bounded-run
  authorisation.
- **Requests carry only** the desensitised manuscript excerpts needed for
  a suggestion — no names, affiliations, project numbers, or material
  outside the pilot paper.
- **Budget:** a per-pilot token ceiling, counted and recorded per request
  batch (Phase 3's bounded run counted 5,136 / 50,000 authorised tokens;
  the pilot sets its own ceiling in the authorisation record).
- **Timeouts and errors:** every model call carries a timeout; a failure
  is classified retryable (network/timeout/5xx) or not (refusal, policy,
  auth) at the call boundary; retry uses backoff with a bounded count.
- **Fallback:** on exhausted retries the loop offers the substitute model
  path; substitute output is labelled as substitute and never recorded as
  the real model's result (plan §7.2).
- **Stop conditions:** the loop stops on budget exhaustion, repeated
  refusal, or owner cancellation, and says which stop fired in the run
  record.

## 6. Pilot data model — link fields

The pilot must let one trial task be traced from input version to output
version to the four deliverables, with every problem record pointing back
into that trace (plan §5 completion condition 3, §9.4):

- **Task** — id, title, workspace, input version id, current stage, timestamps.
- **Opinion** — id, task id, source locator (document part + anchor),
  advisor text reference (by id/digest, not copied into free records),
  status (`pending | accepted | partial | rejected | need-evidence`),
  linked suggestion ids.
- **Suggestion** — id, opinion id, model id, model output reference,
  approval record id, apply result id.
- **Version** — id, task id, kind (`input | working | output`), digest,
  parent version id, created-by, created-at.
- **Deliverable** — id, task id, kind (`marked | clean | reply-table |
  quality-report`), output version id, file digest, export record id.
- **Issue** — id, task id, stage, severity
  (`blocking | severe | normal | suggestion`), type
  (`function | ui | performance | model | documentation`), linked
  opinion/deliverable ids, status, fix version.
- **Approval** — id, suggestion id, approver, decision, decided-at,
  applied-version id.

Every link is an id, never a copy of content, so the trace stays intact
when material is withdrawn or records are archived.

## 7. Completion conditions (plan §5, restated)

- [x] Every Phase 3 carried item has a Phase 4 owner or an explicit
      later-phase attribution (§2).
- [x] The pilot material can be verified in the authorised environment,
      and the repository keeps only desensitised metadata and fixtures
      (§4).
- [x] One trial task is traceable from input version to output version and
      the four deliverables on paper (§6) — the field list is the contract
      the P4-CAP implementation must satisfy.
- [x] The Phase 3 board's top status no longer carries stale wording
      (board-row updates land with this ticket's commits).
- [ ] Baseline version + environment frozen and witnessed by a tagged
      record (§3) — completed when the pilot's first release notes cite
      this section's identities.
- [ ] Real-model authorisation record signed (§5) — before P4-CAP's
      real-model step runs.
