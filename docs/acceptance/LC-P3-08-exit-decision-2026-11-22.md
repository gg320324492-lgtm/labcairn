# LC-P3-08 exit decision — 2026-11-22 (owner signs at T10)

**Record class:** owner decision record — not trial evidence, not a review.
Safe fields only: digests, counts, ids, refusal-class names, host versions,
printed commit SHAs. No sample prose, no comment bodies, no tracked-change
text, no replies, no model prose.

**Signing prerequisites** (EXIT-PREAUTH "does not do" #3): T8's trial record
and T9's signed review both exist in this repository at the commit this
decision names — held.

**Pre-authorization** (`E:/labcairn-local/p308-trial-run/EXIT-PREAUTH.md`,
owner, 2026-11-15): PASS WITH NOTES when all eight §4 rows pass on their own
evidence and the only items standing are the row-7 named gap and the
recorded limits; PASS only when no gap remains; a blocker keeps the decision
blocked; a row failing its deciding rule fails the trial; every other
outcome comes back to the owner on the evidence.

## Field 1 — Verdict

```text
Verdict: PASS WITH NOTES
```

The owner's ruling at signing: the trial's evidence shows **no blocker and
no row failing its deciding rule**. The routed defect the review raised
(strip-stage OOXML malformation) was **fixed, witnessed and verified the
same day** (commit `ce1f2f0…`; dual-host reopen of the fixed strip's output
without a repair prompt; carried in the 0.0.3 installer and smoked). The
remaining items are **measured gaps honestly recorded** — the build's loop
is the analysis loop, so the delivery-shaped rows (1/3/4/6) cannot show
their full passing conditions, row 5's injected-class coverage is six of
seven, and row 8's distribution record was not refilled for 0.0.2 — plus
the row-7 named gap held open under §14 item 7 while LC-P3-06 is BLOCKED.
The owner, on the evidence, **widens the pre-authorization's narrow
"only row-7 stands" condition to admit these recorded measured gaps as
carried obligations**: Phase 3 closes with them, each with its closing
condition. This widening is the owner's own decision made at signing, on
the assembled evidence — not a reader's conversion of a blocker.

## Field 2 — The commit the decision reads

```text
Commit read by this decision: 15c7a18993e51c8b529eebd067148bc6dc21b557
```

Printed by `git rev-parse HEAD` immediately before this record was written.
The trial record (with the strip-fix close-out) and the signed review form
both stand at this commit; the review read the trial record at its own
printed commit `268d6793e5e5eb81fbb0539401a806d37aea139b`, and the only
commits between are the review forms themselves, the CJK-ceiling
registrations, the strip fix and its witnesses, and this record's own
close-out updates — none of which changes the trial-day evidence.

## Field 3 — Per-row status of the eight §4 rows

```text
Row 1 — import→delivery (one triple across the four deliverables):
  Status: measured gap (the loop ran end to end on the real stripped
          manuscript with consent; the four-deliverable binding is not
          observable in this build — no apply/publish stage)
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 1"
          @15c7a18…; T3 record sha256 fb5628aa…; analysis artifacts
          01a1fe2a….{figure.svg,manifest.json}
Row 2 — original/format (pre/post digests equal; dual-host reopen without repair):
  Status: pass on its deciding rule — pre/post digest equality holds
          (7027b184… before and after); the routed defect the review found
          (strip output malformed; Word refuses) was FIXED at ce1f2f0…
          with witnesses, and the fixed strip's output reopens on both
          hosts with no repair prompt
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 2"
          @15c7a18…; T6 record sha256 46e6dc3b…; screenshots
          E:/labcairn-local/p308-trial-run/screenshots/ (9 files)
Row 3 — point-by-point response (locate + four-way decision):
  Status: measured gap (four-way decision recorded, D-001 pending; the
          location half is an honest empty set — this build's loop emits
          no prose suggestions)
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 3"
          @15c7a18…; response record sha256 d61d157e…
Row 4 — research quality (three named cases, independent statuses):
  Status: measured gap (the three-case shape is not produced by this
          build's analysis loop; only D-001 pending exists)
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 4"
          @15c7a18…
Row 5 — permission/privacy (seven injected attack classes refused):
  Status: measured gap (six refusal classes observed on the trial machine
          — default_deny, session_required, approval_refused,
          approval_missing, args_changed, arguments_invalid; the seven
          named attack classes were not individually injected; the
          protocol's trial-refusal-record was not filled)
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 5"
          @15c7a18…; T5/T7 record sha256 1528e3a9…
Row 6 — cancel/retry/recovery (two interruption points):
  Status: measured gap (unexercisable in a build with no apply/publish
          stage; no recovery record exists and none is claimed)
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 6"
          @15c7a18…
Row 7 — one real model:
  Status: named gap — held open (per §14 item 7 while LC-P3-06 is BLOCKED;
          LC-P3-06's bounded run is cited as that ticket's own record, not
          a pass)
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 7"
          @15c7a18…; docs/acceptance/LC-P3-06-real-half-2026-11-10.md
Row 8 — distribution/review (installer identity, install/run/rollback):
  Status: pass by citation for the drilled identity + the trial's own
          package installed and ran (T0 four arms PASS); measured gap on
          the unfilled 0.0.2 distribution record
  Record: docs/acceptance/LC-P3-08-trial-record-2026-11-22.md §"Row 8"
          @15c7a18…; LC-P3-05-install-drill-2026-11-14.md; T0 record
          sha256 466f3cd0…
```

## Field 4 — Row-7 named-gap statement

```text
Gap name: row 7 — one real model
Status: named gap — held open
Closing condition: LC-P3-06 unblocks and the installed build runs one
controlled de-identified case with a person reviewing the suggestion
before delivery
Substitute passed this row: NO (never permitted)
Cited context (that ticket's own records, NOT a pass):
  docs/acceptance/LC-P3-06-real-half-2026-11-10.md
  docs/acceptance/LC-P3-06-substitute-first-2026-11-10.md
  (bounded run: 5/20 requests, 5,136/50,000 tokens, two locatable
   suggestions, gaps G4/G7 — cited as context only)
```

## Field 5 — Carried notes / limits list

From `docs/plans/LC-P3-07-known-limits-2026-11-14.md` (all items):
the killed-write temp file on Windows; the locked original reported as
`source_changed`; the per-run stop-loss; the real-model timeout row held
as a named gap; the drill-defect D-07-01 (fixed for 0.0.2+); the
design-stated limits the drills confirmed; the deferred items with owners.

From this trial's own list (trial record §"Limits this trial adds"):
1. strip-stage OOXML malformation — **FIXED at `ce1f2f0…`**, closing
   condition met, carried as closed;
2. no apply/publish stage in this build (rows 1/3/6) — closes when the
   stage lands and the four-deliverable binding is demonstrated;
3. row-7 named gap — held open per §14 item 7;
4. first-launch supply gap — adjudicated **closed for 0.0.2+** (the
   install materializes a live `shell-env.json`; T0 arm A; install tree
   confirmed), carried as closed;
5. row 5's class-coverage delta and the refusal evidence's openable
   addresses — closes when each named class is injected and refused at an
   openable address;
6. row 4's three-case shape — closes when the prose-edit/quality stage
   lands;
7. the distribution record refilled for 0.0.2/0.0.3 — closes when filled
   from the T0 arms;
8. the T6 record's "the session" wording — closes with one clarifying
   sentence naming who or what drove the opens.

Protocol §4 seam limit (carried, known limit — not a finding):
`root_kinds={"source"}` — the chain-editing capabilities refuse at output
versions before a rule is asked; the product's actual chain-fill behaviour
is `labcairn.papers.binding._fill_chain`. Confirmed carried.

## Field 6 — Blocker evidence addresses

```text
Blockers: NONE
```

The review's classification at the read commit: 0 blocker; 1 routed defect
(C-01, strip-stage OOXML malformation) — **closed by the fix at
`ce1f2f0…`**; 9 measured gaps, of which C-06 (first-launch supply gap) was
adjudicated closed during the review on the install-tree evidence and C-01
is closed as above. No finding classified `blocker` stands; nothing was
converted from a blocker by any reader.

## Field 7 — Review-completeness statement

```text
Review complete at the Field-2 commit (both forms in the tree):
  Named human reviewer (Reader A): LabCairn (the project owner;
    designated by the owner on 2026-11-16; owner ruling 2026-11-21 that
    the reviewer designation across the trial records is LabCairn)
  Reviewer form: docs/acceptance/LC-P3-08-review-2026-11-22-1.md
    (A-01…A-09 filled; A-09 signed "LabCairn, 2026-11-22")
  Second reader (Reader B): independent agent session
    local_ddddf50c-40cf-460b-ae40-8acac63ee5f9, fresh context; its
    filled B-side form:
    docs/acceptance/LC-P3-08-review-2026-11-22-readerB.md
  Second reader's disclosure (F-08/B-03, verbatim, cmp-verified
    byte-identical, 92 bytes): "independent agent session stood in for a
    human reader; no human being performed this reading"
  F-06's disclosed cost: the owner is also this trial's participant and
    advisor, so the real-advisor rows are self-read by a human — no
    second pair of eyes on them; accepted by the owner.
  Arbitration: NONE — no disagreement (no D-row engaged; the one
    contradiction Reader B raised, C-B9, was adjudicated by Reader A on
    the install-tree evidence and recorded in C-06)
```

## Field 8 — Sample and build fingerprints

```text
Sample actually trialed (owner decision 2026-11-21: reuse
material-batch-5; the protocol §1's drilled sample 9154e56c… was
superseded by that decision and is not this trial's sample):
  advisor-annotated working sample:
    MNBs氯消毒大肠杆菌5批注.docx
    sha256 a7a38132cf35d3632c4cb8aacba910994e9ad7e8b27413761260ade2d6502278
    8,871,367 B — measured 2026-11-21/22, matches T1 supply receipt
    (T1-SUPPLY-RECORD-20261121.json, sha256 23622d2d…) and the batch-5
    fingerprint library
  stripped loop input: sha256 7027b184… (8,804,648 B), digest equality
    before/after the loop verified three ways
  fixed-strip output (product fix ce1f2f0…): sha256 42eefb06…
    (8,804,644 B), well-formed, dual-host reopen without a repair prompt
Installer actually trialed: LabCairn Setup 0.0.2.exe, sha256
  8d38177b5638e7b85f7b505438ab3321586c4320f21258f0b3da5275785cbda1,
  354,088,311 B, built from main b90e2b53… — measured 2026-11-21/22,
  matches installer/SHA256SUMS.txt and BUILD-SOURCE.txt
Installer carrying the strip fix (built after the review, smoked):
  LabCairn Setup 0.0.3.exe, sha256
  681607c7de0a2963016ff461e8999cef4fda369fa27b896475b70f6466874588,
  354,088,228 B, built from main ce1f2f0…; install/HKCU registration/
  shell-env materialization/uninstall smoke passed 2026-11-22
```

## Field 9 — Phase 3 closing statement

Phase 3 closes with those named gaps and limits carried forward as
recorded obligations, each with its closing condition.

## The owner's signature

```text
Owner (participant, advisor, and named reviewer's designator):
  signed 2026-11-22, at commit 15c7a18993e51c8b529eebd067148bc6dc21b557
Verdict: PASS WITH NOTES
Scope: closes Phase 3's §4 acceptance. Does not close LC-P3-06, does not
  rewrite Phase 2's real_model_smoke = NOT RUN, and does not release
  row 7's closing condition.
```
