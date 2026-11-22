# LC-P3-08 trial record — the G4 trial as run (2026-11-21/22)

**Date:** 2026-11-21 (T0–T5, T7) and 2026-11-22 (T6). **Machine:**
`DESKTOP-BJJHSDF`. **Participant:** the owner (the owner's 2026-11-21
decision). **Reviewer designation:** LabCairn (owner ruling 2026-11-21,
repository commit `1d52ef3`).
**Status:** TRIAL RUN COMPLETE — records assembled; the exit decision
awaits T9 (independent review) and T10 (owner's signed verdict).

**This record names its own commit:** it is written at
`<COMMIT-SHA-TO-BE-FILLED-AT-COMMIT-TIME>` on `main`. Execution plan §9
forbids quoting an unprinted SHA; the commit line is printed when this
file is committed, and the T9 reviewers read the record at that commit.

## Sample and roles (fingerprint-identified)

The advisor's real sample, drawn from material-batch-5 (fingerprint
library `E:/labcairn-local/batch-fingerprints.json`), supplied by the
owner in the advisor seat on 2026-11-21
(`E:/trial-material/advisor-sample/T1-SUPPLY-RECORD-20261121.json`,
sha256 `23622d2d078f65c149a1cca19a7af18d4aaf7c86bd710d1e5968001f82dc2bc0`):

| file | role | bytes | sha256 |
|---|---|---|---|
| `MNBs氯消毒大肠杆菌4.0.docx` | student-original (pre-advisor base) | 1 496 950 | `95a7e977b1f420bb5fab1f610a7c2e4b919adb76c76fa6e111bc85914e2980c2` |
| `MNBs氯消毒大肠杆菌5批注.docx` | advisor-annotated (the trial's working sample) | 8 871 367 | `a7a38132cf35d3632c4cb8aacba910994e9ad7e8b27413761260ade2d6502278` |
| `MNBs氯消毒大肠杆菌7批注.docx` | advisor-annotated (second batch copy) | 10 815 179 | `0d1a6eb555d6105fcfa08edecb2aa09efe3dc6b293ddb9d10048acbddf841c49` |

The advisor's marks in the working sample: **91 sentence-level
insertions and 15 deletions** (tracked revisions) plus review markers —
the baseline recorded at
`E:/trial-material/trial-workspace/advisor-revisions-baseline.json`.

**Build identity.** The trial ran on the installed package
**`LabCairn Setup 0.0.2.exe`**, sha256
`8d38177b5638e7b85f7b505438ab3321586c4320f21258f0b3da5275785cbda1`,
built from `main` at `b90e2b53d4aab79f4ec36a3e15a17537b8c7bbeb` (the B9
preload fix). Checksums:
`E:/labcairn-local/p308-trial-run/installer/SHA256SUMS.txt`; build
source: `installer/BUILD-SOURCE.txt`.

**Trial workspace:** `E:/trial-material/trial-workspace/` (task
`01a1fe12-fd9f-764f-8bcf-f5cbd57bdcf6`, source
`src-7aeb09482c91283a`). **Stripped manuscript**
(`MNBs氯消毒大肠杆菌5批注-stripped.docx`, the loop's input):
sha256 `7027b1843ebf34ac14050cca4f4f7682881e6229b7a79bf7510a83d8f45ebdaf`,
8 804 648 B.

## Per-row evidence table

Each row names its evidence addresses (working files under
`E:/labcairn-local/p308-trial-run/`), the deciding observation, and the
verdict the deciding rule yields. Raw material never enters the
repository; the working files carry it, and this record cites them by
path + digest.

### Row 1 — Import to delivery — **PARTIAL (named gap)**

- The commented sample was imported and bound to one task
  (`01a1fe12-fd9f-764f-8bcf-f5cbd57bdcf6`), one input version
  (`src-7aeb09482c91283a`, content sha256 `7027b184…`), and the loop ran
  end to end through the consent gate (evidence:
  `T3-TRIAL-RECORD-20261121.md`, sha256
  `fb5628aa30af9c4c61f6f03808f9bfdc286aa1a4c30120cb9c2ae1e490a354ff`).
- **What this build cannot do:** the CLI surface carries **no
  apply/publish stage** — no marked draft, no clean draft, no four-
  deliverable export. The loop's output is the analysis figure + manifest
  (`output/01a1fe12-fd9f-764f-8bcf-f5cbd57bdcf6/analysis/
  labcairn.analysis.grouped_aggregate/01a1fe2a21537134b270dad04e611c77.
  {figure.svg,manifest.json}`). A delivery binding of four deliverables
  to one triple is **not observable in this build** — recorded as the
  trial's named gap for this row, not a pass.

### Row 2 — Original/format — **PASS on digest; PASS both-host reopen on the repaired copy; named defect on the as-delivered strip output**

- **Pre/post digest equality (deciding rule): PASS** — before the loop
  `7027b184…`, after the loop `7027b184…` (CLI `sources inspect`,
  re-measured 2026-11-22; a difference would fail the row outright).
- **Both-host reopen:** WPS Office 12.1.0.29690 opened and reopened the
  stripped manuscript with no repair prompt. **Word 2019
  (16.0.17932.21140) refused the as-delivered stripped file** — the
  strip stage had swallowed four XML close tags at two sites (paragraphs
  `4EE1235F` and `3B06307A`), leaving malformed OOXML that WPS masks and
  Word rejects. After a minimal content-preserving repair (four close
  tags restored; repaired copy sha256
  `14886be3070ff6c60758d9f105ff3a74854901137ef8ab21fe74eaeca53b7353`),
  **both hosts opened and reopened with no repair prompt**.
- **Non-target class counts (before → after):** tables 25 → 25,
  images 7 → 7, fields 4 → 4, media parts 8 → 8, tracked revisions
  113 → 0 (removed by design), body-text 1 698 → 1 683 (the deleted
  revisions' runs); equations/text-boxes/content-controls 0 → 0. No
  surviving diff outside the approved edit set.
- **Support-matrix boundary:** no change outside the support matrix; the
  loop wrote nothing to the original (digest equality above).
- Evidence: `T6-REOPEN-RECORD-20261122.md` (sha256
  `46e6dc3be9fef973eea72a874f65cde8f51fb61d9574d7d13aa767582c9c0a9c`) +
  screenshots `E:/labcairn-local/p308-trial-run/screenshots/t6-*.png`
  (7 files, including the Word refusal dialog).

### Row 3 — Point-by-point response — **PARTIAL (honest empty location set; decisions recorded)**

- The response record
  (`trial-response-record-20261121.md`, sha256
  `d61d157e7e0f3ab2a286fbee7f5a5fe93a37e2d57e7a67a3d977303ac6b03c3e`)
  covers the advisor's marks at the level this build operates: the loop
  is a data-analysis loop and emits **no prose revision suggestions**, so
  the location half is an **honest empty set** — no opinion id was
  located to a prose edit, and none was marked located.
- D-001 (the grouped-aggregate analysis over the manuscript's own
  tabular data) carries status **pending** with its evidence address
  (figure + manifest digests). The four statuses are available and the
  recorded state uses them; the automatic-edit linkage (opinion →
  evidence → operator → version) is not exercisable without prose
  suggestions — part of the same named gap as row 1.

### Row 4 — Research quality — **PARTIAL (three-case shape not produced by this build)**

- The directly-editable / needs-further-evidence / uncertain-location
  case shape is defined for prose-edit suggestions. This build's loop
  produced one analysis case (D-001) whose UNCERTAIN handling is
  demonstrated in T7's refusal chain, not by a research-quality
  classification. Recorded as the build-level limit; the row's verdict
  waits for the exit decision on the evidence as it stands.

### Row 5 — Policy refusals — **PASS (observed refusals on the trial machine)**

- `T5-T7-TRIAL-RECORD-20261121.md` (sha256
  `1528e3a911bd6d6e010d9d046bffb3871ca48cb3e18400f6d6538741d66e4395`)
  records six observed refusal classes, each with the command that
  produced it: unlisted read → `default_deny` (the `task report` render
  refused on the manifest artifact); write without session token →
  `session_required`; double-grant → `approval_refused`; unknown
  approval id → `approval_missing`; args changed after grant →
  `args_changed` (three times); wrong capability/argument shapes →
  `arguments_invalid` (three recipe-schema refusals: `kind`-free rows,
  missing `caption`, missing `selection.source`).
- The seven injected attack classes of protocol §3 row 5 (cross-project
  reference, path escape, write to the original, forged approval,
  expired approval, unauthorised outbound, embedded instructions) were
  **not individually injected on the trial day**; the consent mechanism's
  refusal behaviour was exercised through the six observed classes
  above. The gap between the seven named classes and the six observed
  ones is recorded for the reviewers' judgement.

### Row 6 — Cancel, retry and recovery — **NOT EXERCISED (named gap)**

- The two side-effectful interruption points around publication cannot
  be exercised in a build with no apply/publish stage. No recovery
  record exists; the row carries no passing evidence and is not claimed.

### Row 7 — One real model — **NAMED GAP (held open per §14 item 7)**

- Per the owner's §14 item 7 answer, this row **stays a named gap** while
  `LC-P3-06` is `BLOCKED`. No substitute was run; LC-P3-06's bounded
  real-model run (5 requests, 0 refused, 0 failed, 5 136 / 50 000
  authorised tokens, seven measured gaps —
  `LC-P3-06-real-half-2026-11-10.md`) is cited as that ticket's own
  bounded run, not as this row's pass. Closing condition: LC-P3-06
  unblocked and the row run on the installed build.

### Row 8 — Install, rollback, distribution — **PASS by citation (drilled), supply gap carried**

- The installer drill it cites is
  `LC-P3-05-install-drill-2026-11-14.md` (installer
  `LabCairn Setup 0.0.0.exe`, 234 325 233 B, sha256
  `9805be54821ae8af549bb7cd2e3c9924186550127005130004680e4ff5e155c4`,
  drilled from `main` at `7a44f569ceafb4c5c284c183e764f53b8f6ad1af`).
- The trial's own package (`0.0.2`, sha256 `8d38177b…`) was installed and
  ran the trial loop (T0 four-arm precondition PASS —
  `T0-PRECONDITION-RECORD-0.0.2-20261121.md`, sha256
  `466f3cd0ba06279dfd7beb19034bbf41d32181d2298a5e99b0648112be29e685`).
- Known supply gap carried into the limits list: the installed package
  ships `shell-env.template.json` and no `shell-env.json`, so first
  launch needs one operator action.

## Cross-citation — LC-P3-02 real-sample record (cited, not claimed)

The 42-arm machine loop on the earlier real sample is
[`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md):
**42/42 arms measured; complete = true; report sha256
`a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638`;
human dual-host reopen: 16/16 PASS on 2026-11-16/17** (sixteen rows,
hashes unchanged, ledger sha256 `2d8b133b…`, 27 107 B). That record's
sample (`9154e56c…`) is not this trial's sample (`a7a38132…` /
stripped `7027b184…`); the citation is the earlier measurement's own
evidence, and this trial's reopen evidence stands separately above.

## The seam statement (verbatim from protocol §4)

> The chain-editing capabilities `labcairn.papers.revisions.record_revision_events`
> and `labcairn.papers.feedback.record_feedback`, when addressed at an output
> version, refuse before a rule is asked — the capability registry's
> `root_kinds={"source"}` means the listing does not show output versions.
> This is a known limit, not a defect, and widening the capability's root
> kinds before the trial was not authorised. The product's actual chain-fill
> behaviour is `labcairn.papers.binding._fill_chain`: it mints the chain's
> edit rows from the approval records through the store's own writers, with
> the actor `model` and the grade `human_verified`, keeping every vocabulary
> and grant check. The dossier carries those rows; the trajectory panel
> shows the input round's rows.

## Limits this trial adds to the recorded list

1. **Strip-stage OOXML malformation (new, found by this trial):** the
   strip stage's output carried two malformed `document.xml` sites
   (four missing close tags) that Word 2019 refuses. Found by the
   dual-host reopen; repaired for the trial to proceed; the repair is
   recorded with before/after digests. Closing condition: the strip
   stage emits well-formed OOXML by construction.
2. **No apply/publish stage in this build** (rows 1/3/6 partial or
   unexercised): the loop ends at the analysis artifacts. Closing
   condition: the apply/publish stage lands and the four-deliverable
   binding is demonstrated.
3. **Row-7 named gap** held open per §14 item 7 while LC-P3-06 is
   `BLOCKED`.
4. **First-launch supply gap** (carried from LC-P3-05): the installed
   package ships `shell-env.template.json` only.

## Where the raw evidence lives

All raw material stays in the authorised environment outside the
repository: `E:/trial-material/` (samples, stripped and repaired
manuscripts, trial workspace with the database, serve logs, recipe,
analysis artifacts) and `E:/labcairn-local/p308-trial-run/` (records,
installer, screenshots). This repository record carries digests, counts,
refusal class names, version ids and paths — no material text. The
per-output-file boundary check is
`E:/labcairn-local/g4-templates-prefilled-20261117/templates/trial-evidence-boundary-record.md`,
filled 2026-11-22 beside this record's working copy.
