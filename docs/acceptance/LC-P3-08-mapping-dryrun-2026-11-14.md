# LC-P3-08 — §4 evidence-mapping dry run (2026-11-14)

**Record class:** DRY RUN — a paper exercise against the mapping, not a
trial result. A rehearsal is not a trial result and is labelled as one
([`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §13 §6.8
permitted half: "a dry-run of the §4 mapping"; no dev-build rehearsal is
authorised under §12 decision 2, and none was run — this dry run is a
*desk check of the protocol's decidability*, executed on the protocol and
the existing acceptance records, not on a build).

**Date:** 2026-11-14.
**Object under test:** [`LC-P3-08-trial-protocol-2026-11-14.md`](LC-P3-08-trial-protocol-2026-11-14.md)
§3's per-row evidence map (this worktree, branch
`claude/silly-margulis-65e484`, HEAD
`a7cde5999a9db1524e2ec5514685b449e43de4b1`, printed by `git rev-parse HEAD`
before the dry run started).
**Authorities read as data:** [`PHASE_3-execution-plan.md`](../plans/PHASE_3-execution-plan.md)
§4 and §9; [`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §13
§§6.1–6.8, the 2026-11-10 owner decisions, §12 decisions 2/5, §14 item 7;
[`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md)
§§2–3, §5; the three LC-P3-08 design documents of 2026-11-10; the dated
records [`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md),
[`LC-P3-06-real-half-2026-11-10.md`](LC-P3-06-real-half-2026-11-10.md),
[`LC-P3-06-substitute-first-2026-11-10.md`](LC-P3-06-substitute-first-2026-11-10.md),
[`LC-P3-05-install-drill-2026-11-14.md`](LC-P3-05-install-drill-2026-11-14.md),
[`LC-P3-02-support-matrix.md`](LC-P3-02-support-matrix.md).
**Prior dry runs read as data:** the reviewer-form synthetic dry run of
2026-11-10 (`E:\labcairn-local\phase3-g1-evidence\LC-P3-08-form-dryrun-2026-11-10.md`,
outside the repository) — its FO-01 precedence ruling and FO-07 address
findings are re-checked here against the protocol now in the tree.

**Question the dry run answers:** is every §4 row's evidence requirement
**decidable** — can a reviewer, holding the trial record this protocol
demands, reach exactly one verdict per row without inventing a rule after
the fact?

**Result: PASS WITH NOTES.** All eight rows plus the closing sample-class
rule are decidable as mapped. Three notes are carried forward as obligations
on the trial record (N-1, N-2, N-3 below); none blocks the protocol.

## 1. Method

For each row, four questions were asked against the protocol's own text:

1. **Requirement** — does the row name the observations its §4 passing
   condition needs?
2. **Deciding rule** — is the pass/fail rule stated before the trial, in
   words a reviewer can apply without new judgement?
3. **Output file** — is the record shape named, with fields sufficient to
   carry the evidence?
4. **Address shape** — can every citation be written in the fixed form
   `path + section anchor + digest/count/refusal class`?

A row is **decidable** when all four hold. A row is **ambiguous** where two
readings of the protocol text lead to different verdicts on the same
record. A row is **unmeasurable** where its evidence cannot exist in any
record the protocol allows.

## 2. Per-row dry-run verdicts

| §4 row | Requirement present | Deciding rule | Output file fields | Address shape | Verdict |
|---|---|---|---|---|---|
| Import to delivery | Yes — four deliverables, one triple | Yes — binding equality per deliverable; any mismatch fails | Yes — task/version ids, digests, receipts | Yes | **DECIDABLE** |
| Original and format | Yes — hash, reopen, clean-draft match, non-target survival, refusal/handover | Yes — digest equality required; per-file open/reopen classes; silent out-of-matrix application fails | Yes — pre/post digests, host results, class counts, refusal/handover names | Yes — host observations carry the authorised path outside the repo | **DECIDABLE** |
| Point-by-point response | Yes — per-opinion location + status + edit links + separate records | Yes — no blank location; four statuses as separate entries; missing link fails; merged record fails | Yes — per-opinion and per-decision ids | Yes | **DECIDABLE** |
| Research quality | Yes — three case classes, missing items, two statuses | Yes — independent statuses with own addresses; pass-with-unresolved-task fails | Yes — case ids, task ids, two status fields | Yes | **DECIDABLE** |
| Permission and privacy | Yes — six refusal classes + de-identification + safe fields | Yes — per-class injected case + observed refusal; missing class fails; material text fails and is H-03 | Yes — class names, case ids, safe-field list | Yes | **DECIDABLE** |
| Cancel, retry and recovery | Yes — two interruptions, three outcome classes, receipt uniqueness | Yes — outcome class per interruption; digest equality; duplicate receipt fails | Yes — interruption ids, states, digests, receipt sets | Yes | **DECIDABLE** |
| One real model | Yes — but its §4 evidence is owner-gated | Yes — **PENDING-OWNER as a named gap** per §14 item 7; substitute never passes; 06's halves cited as context, not converted | Yes — gap record with closing condition and citations | Yes | **DECIDABLE AS A NAMED GAP** — see N-2 |
| Distribution and review | Yes — install/rollback, identity, case results, limits, blocker clause | Yes — blocker classes keep the decision blocked; the installer drill's values are cited, not re-measured | Yes — build identity, results, comparison, ids, limits | Yes — package digest `9805be54…55c4` printed in [`LC-P3-05-install-drill-2026-11-14.md`](LC-P3-05-install-drill-2026-11-14.md) | **DECIDABLE** |
| Sample-class closing rule | Yes — raw material stays out | Yes — per-file raw-location + safe-field list + absence check; material text fails | Yes — `trial-evidence-boundary-record` | Yes | **DECIDABLE** |

## 3. The three named-gap / honesty interactions the dry run re-checked

The 2026-11-10 form dry run's two structural findings were re-tested
against the protocol as now written:

- **Precedence (FO-01).** The held-open "One real model" row satisfies the
  naive `blocker` predicate ("the trial record cannot show a §4 row its
  passing condition requires") *and* the named-gap predicate. The reviewer
  form design now carries the carve-out: an owner-authorised named gap
  under §12 decision 5 / §14 item 7 is `measured gap`, not `blocker`. The
  protocol repeats the ruling at its Row 7, so a reviewer reading the
  protocol alone reaches the same class. **Re-tested: consistent.**
- **Address shape (FO-07).** The blocker standard, the mapping design §3
  and the protocol's address shapes all now reduce to one form: `path +
  section anchor + identifying digest/count/refusal class` (+ printed full
  SHA where the record is in the repository). The protocol's §6 repeats the
  discipline. **Re-tested: consistent.**

## 4. Decidability probes on the existing records

To show the deciding rules bind to real observations (not only to future
ones), each rule was probed against a record that already exists:

| Probe | Record read | Rule applied | Outcome |
|---|---|---|---|
| Fingerprint-only naming | [`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md) | Sample-class closing rule | The record carries sha256, byte size and counts, no prose — **passes** the rule as a citation source |
| Refusal-class citation | same record (28 refused arms; [`LC-P3-02-support-matrix.md`](LC-P3-02-support-matrix.md) classes) | Row 3 and Row 5 citation surface | Class names + counts are citable safe fields; the mapping design §2's field table covers every field the record prints — **decidable** |
| Budget figures as citation | [`LC-P3-06-real-half-2026-11-10.md`](LC-P3-06-real-half-2026-11-10.md) (5/20 requests, 5 136/50 000 tokens) | Row 7 named-gap citation | Figures are counts with a printed record address; the gap record can cite them without converting 06's run into a trial row — **decidable** |
| Installer identity as citation | [`LC-P3-05-install-drill-2026-11-14.md`](LC-P3-05-install-drill-2026-11-14.md) | Row 8 | Package name, size, sha256, install/uninstall/reinstall results and the `shell-env.json` supply gap are all printed with their commands — **decidable**; the supply gap enters the limits list as a known limit |
| Host-version requirement | [`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md) §5 | Row 2 | WPS Office primary / Office 2010 reference are named hosts; live re-measurement is required at trial time, so the address shape (authorised path + version strings) is satisfiable — **decidable** |

## 5. Notes carried forward to the trial record (obligations, not defects)

- **N-1 — Receipt/digest namespace.** Rows 1, 2 and 6 all quote digests.
  The trial record must prefix every digest with what it digests
  (`original`, `marked-draft`, `clean-draft`, `table`, `report`,
  `installer`, …). Two bare sha256 values in one record would be
  unattributable. The output-file field lists already name each digest;
  the trial record must not flatten them.
- **N-2 — The named-gap row's exact wording.** Row 7's gap record must
  state the closing condition verbatim from §14 item 7's shape: the row
  closes when the installed build runs one controlled de-identified case
  whose model returns at least one locatable, reviewable suggestion that a
  person reviews before delivery, under a live budget/permission/degraded-
  path demonstration. Until then it stays `measured gap` at every exit-
  decision reading, whatever else passes.
- **N-3 — Cross-reference is field-level.** When the trial record cites
  02's real-sample record, it cites fields (fingerprint, counts, refusal
  classes, status labels) with the mutual anchor of the mapping design §3 —
  and 02's record must gain the reverse pointer naming 08's trial record as
  the consumer. The reverse link is a decision-3 obligation on the trial
  batch, tracked here so it is not lost.

## 6. What this dry run does not do

It runs no product code, launches no build, opens no Word host, spends no
provider request, touches no real participant, and writes no trial row, no
review finding, no classification and no exit verdict. It enters nothing
into any §4 row. Its probe readings are citations of existing dated
records, not new measurements. It authorises no push, no pull request, no
CI run.
