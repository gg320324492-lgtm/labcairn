# Review checklist — lessons of the 2026-11-14 multi-round review

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commits named below; the tree moves. Follow the sentence,
not the number.

**Anchors, printed live while this record was written** — every commit SHA
below was produced on 2026-11-14 by `git log --format=%H` on this machine,
from the tree at `main` = `dfb63cd274f7c0189126d12af65cae2a276a44d4`; none was
carried from another record.

**Purpose.** This checklist distils the review rounds of 2026-11-14 into six
checkable items. Each item names a failure that really happened today (a CI
run went red, or a review caught a live gap), the repair commit that fixed it,
and the question a reviewer asks at the next gate. A review window dispatched
for a Phase 3 gate reads this list before it starts and answers every checkbox
against the diff it reviews.

---

## R1. A witness must not depend on a build artifact the runner does not have

- [ ] Every witness in this diff runs green on a bare runner — no test reads a
      file that only exists after a local packaging, freeze or install step
      (`shell/build/`, `dist*/`, a PyInstaller output, an installed
      directory). If the property needs a frozen tree, the witness **builds a
      synthetic one in its own temp directory** rather than reaching for a
      real artifact.
- **Where it went red today:** three packaging-guard cases in
  `shell/test/packaging-config.test.mjs` read the real frozen backend and the
  real `shell/build/` outputs; the CI runner has neither, and CI went red for
  three consecutive runs.
- **Repair:** `6c176f994e8df3c56dafeea0381c9aff12d37e42` — *Make the
  packaging-guard witnesses use a synthetic frozen tree*.
- **Reviewer's question:** *if I delete every build output on this machine,
  does this witness still run, and still mean something?*

## R2. A witness must not hard-code a single platform's facts

- [ ] No assertion names a platform-specific filename, path separator or
      binary name without deriving it from the platform (e.g. the CLI entry is
      `labcairn.exe` on Windows but `labcairn` on Ubuntu). Freeze/package
      layout facts come from the same constants the implementation uses.
- **Where it went red today:** the hollow-backend witness asserted the
  Windows-only `labcairn.exe` name unconditionally; on Ubuntu the entry
  binary is `labcairn`, and two assertions went red.
- **Repair:** `6e208225906744450968dc6c69c4319a910027b9` — *Make the packaging
  witnesses platform-honest about the freeze*; `7a44f569ceafb4c5c284c183e764f53b8f6ad1af`
  — *Use the platform's entry binary in the hollow-backend witness, too*.
- **Reviewer's question:** *does this assertion survive on the other platform
  in the matrix, or is it quoting one machine's filesystem?*

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

- [ ] **Injection-type defences** (an environment flag, a header, a spawn
      argument) carry **two** witnesses: a static one that watches the value
      is actually set at the call site, and a dynamic one that observes the
      effect on the receiving side. One alone can be deleted and the tree
      stays green.
- [ ] **Connection-type claims** ("when X is skipped, control flows through
      function F") are witnessed as **syntax at the call site**, not only as a
      behavioural assertion inside the arm that CI skips — a witness that only
      executes on the skipped arm is a witness CI never runs.
- **Where it went red / was caught today:** the frozen backend's
  `PYDANTIC_DISABLE_PLUGINS=1` injection had no witness at all until review
  caught it; and the channel-skip test asserted the skip connection only
  inside the skipped arm, so CI never executed it.
- **Repair:** `8bf367a6a64712b9f092fe41e463636e120f261f` — *Watch the frozen
  backend's PYDANTIC_DISABLE_PLUGINS injection*; `f2479c410b6bc487715bcab5a6addb3f3e7234e5`
  — *Watch the channel-skip connection as syntax, not as a sentence* (the
  count/list watching itself came in earlier the same day as
  `1c654212ffb848704ca827c7a016f34473a06f51`).
- **Reviewer's question:** *if someone deletes this defence tomorrow, which
  test in this diff fails — and does that test run on CI, or only on the arm
  CI skips?*

## R4. Quoting external material: English paraphrase plus provenance, never the original non-English wording

- [ ] A record that needs to reproduce wording from **external material**
      (a court decision, a paper, an advisor's note) writes the quotation **in
      English**, and names **where** the wording lives and **when** it was
      read/measured. The original non-English text is not pasted into any
      tracked file.
- **Where it went red today:** the LC-P3-05 drill record quoted the D17
  wording in its original Chinese; the reference-exclusion and
  release-contents gates both fired on it.
- **Repair:** `22232e2e877c9ddd09c56b5b47f24e12c855cf9e` — *Quote the D17
  wording in English, not in its original Chinese*.
- **Reviewer's question:** *does any string in this diff match the external
  corpus, and is every quotation carried as an English paraphrase with
  provenance and a reading date?*

## R5. A documented rule and its implementation must say the same thing, and both sides need a witness

- [ ] For every behavioural rule a record states ("never X", "always Y"),
      the implementation actually enforces it **in both directions**, and
      there is a test for each direction. A document claiming a rule the code
      only half-implements is a claim with nothing behind it.
- **Where it was caught today:** the workspace-resolution record said the
  workspace is "never an escape" from the installation, but the
  implementation only refused escapes on one side of the path comparison; a
  `..`-climbing path escaped.
- **Repair:** `817a7e54c4890610de84b255f25c7d623f6d4d71` — *Refuse a workspace
  that climbs out of the installation* (with its witness in
  `shell/test/shell-env.test.mjs`).
- **Reviewer's question:** *for each "never/always" sentence in the touched
  records, where is the test that fails when the sentence is false — and does
  it cover both directions?*

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

- [ ] Counts (test cases, packages, files, jobs, bytes) are **measured at
      write time** with the command printed beside the value, and the record
      says **at which commit** the measurement was taken. A number carried
      forward from an older tree is rewritten or re-anchored, not inherited.
- **Where it was caught today:** record files carried file/job counts that no
  longer matched the tree; the sweep at `a691fb699c5c11904bc265cc631ca1db14090e6a`
  corrected the misleading readings, and `c51fb23bba4cbdfb8e795bc71347c176c0b49c25`
  added the map's fresh 2026-11-14 file-count reading with its command.
- **Repair:** `c51fb23bba4cbdfb8e795bc71347c176c0b49c25` — *Add the map's
  2026-11-14 file-count reading*; `a691fb699c5c11904bc265cc631ca1db14090e6a`
  — *Correct the records a 2026-11-14 sweep measured as misleading today*.
- **Reviewer's question:** *for every number in this diff, can I re-run the
  command named beside it at the named commit and get the same value?*

---

## How a review window uses this list

1. Before reviewing, run the six reviewer's questions against the diff under
   review; a "no" on any checkbox is a finding.
2. Record the answers in the review window's own record file, with the
   evidence (test name, command output or commit SHA) beside each answer.
3. If a new failure class appears that this list does not cover, add an R-item
   here in the same delivery, with the red run or review catch that justifies
   it — this list is itself subject to R6.
