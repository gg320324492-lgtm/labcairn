# G1 and G2 — the owner-confirmed review of the checklist

**Status.** The checklist was run and the owner confirmed every row on
2026-11-05. **This is not an independent review in the checklist's sense.**
The checklist requires a reviewer who wrote none of the fixes **and is not
the party that dispatched them**; the owner dispatched this work, so the
second clause is not met. This record says so, and the board's independence
rule for G1 and G2 therefore stays unmet. What this record does carry is the
owner's confirmation of a measured review packet, row by row.

**The packet.** The evidence was produced by a reviewing session against
`6c77a018713bae1a5117e2f9099cb76717f11f21` in the worktree
`claude/nice-swartz-ee3439`, which was left uncommitted and clean. The packet
lives outside the repository at `E:\labcairn-local\G1-G2-review-packet\`
(`REVIEW-SHEET.md`, `SUMMARY.md`); the row-level evidence, the commands and
the mutation results are there.

## 1. The verdicts, as the owner confirmed them

| Option | Meaning | Rows |
|---|---|---|
| **A** | the claim holds: the named mutation reddens the named witness | **21** |
| **B** | the claim holds, with a witness problem that must be recorded | **12** |
| **C** | the claim does not hold | **0** |
| **D** | cannot be confirmed | **0** |

The 33 rows are the checklist's own: G1's 13, G2's 7 + 7 + 6.

## 2. The twelve B rows, and why they are B

**G1**

1. **G1-5** — the checklist names `test_provider_redaction.py` and
   `test_workspace_boundaries.py`; both stay green under the mutation. The
   unapproved-send property is held by
   `tests/test_outbound_consent_bridge.py` (6 red).
2. **G1-6** — the third node,
   `test_a_junction_is_not_reported_as_a_symlink`, asserts a platform
   premise (`Path.is_symlink()` on a junction), not a product behaviour; no
   product mutation can redden it. The other two nodes redden as claimed.
3. **G1-10** — the checklist names `test_fake_provider_usage.py`, which
   tests `usage_from_wire` (record reconstruction); the omitted-usage →
   `Unknown` property is held by
   `test_fake_provider_usage_transcripts.py` (2 red).
4. **G1-11** — the named files stay green; the node that reddens is
   `test_fake_provider_usage_transcripts.py::test_replay_is_strict_about_the_request`
   (1 red), which this packet added.
5. **G1-12** — `security_policy.py` has no dedicated witness; the digest
   cases above carry it, as the checklist says. The claim holds; a dedicated
   witness for the documented "ALLOW cannot change the target" sentence does
   not exist.

**G2**

6. **G2.1-5** — a mutation from `BEGIN IMMEDIATE` to `BEGIN` leaves the 8×6
   concurrency test green (`1 passed`); only the structural assertion
   (G2.1-6) watches race handling, not a behavioural witness.
7. **G2.1-7** — deleting `env.dispose()` leaves both persistence tests
   green; the identity-and-sequence-across-restart claim holds, but the test
   does not distinguish a restart from a reused pool.
8. **G2.2-4** — deleting `assert_replayable`'s `ATTEMPTING` branch leaves the
   whole crash-matrix file green (10 tests).
9. **G2.2-6** — only one arm (`policy_unchanged`) was mutated; the other
   seven refusal reasons were run at baseline only. A per-arm mutation pass
   would be a separate round.
10. **G2.3-3** — the short-circuit reddens 2 of the 5 listed nodes; the other
    three are carried by different mechanisms (handler, closure, schema).
11. **G2.3-4** — disabling the proposal-digest comparison reddens 1 of the 4
    nodes; direct, expired and blocked are carried elsewhere.
12. **G2.3-5** — the retry-cap mutation reddens 2 of 3 nodes; the third
    (`unexpected exception propagates`) is unaffected, which is expected.

## 3. The measured environment, as the packet reports it

- Baseline of the 33 rows: **622 passed, 12 skipped, 0 failed**.
- Door demos: G1 **36 checks**, G2 **14 checks**, G2 uncertain **18
  checks**, all exit 0.
- Static gates: `ruff check .` passed; `ruff format --check .` 445 files;
  `mypy` 397 source files, no issues.
- Whole suite: **5 failed, 4898 passed, 14 skipped** in 46:06 (exit 1). All
  five are clone/wheel subprocess tests; removing the parent process's
  `PYTHONPATH` and re-running that group gives **18 passed**. The record
  keeps the first result and its explanation rather than reporting only the
  second.
- Mutations: each restoration was checked by sha256, and the worktree's
  `git status` was empty after the last one.
- **Windows only**: 12 skips (9 POSIX-only, 1 Windows-drive-form, 2 no-8.3
  volume). The POSIX half of the witnesses was not measured.
- The checklist's §2.3 commit counts do not match the tree exactly
  (`src/labcairn/skills` is 2 commits where the checklist says 1; `core` +
  `runtime` are 13 and include Phase 2 commits). Recorded in the packet; not
  diffed commit by commit.

## 4. What this discharges, and what it does not

- It **discharges** "the checklist was prepared and never executed": the
  checklist has been run against a named commit, every row has a verdict,
  and the twelve rows with witness problems are named.
- It **does not discharge** the board's independence rule: the reviewer is
  the party that dispatched the work. The owner's decision of 2026-11-05
  lets an independent agent session stand in for a human reader, but this
  review was a project session's, so the rule still asks for a later review
  by an independent session that took no part in building the work.

---

## 5. The twelve B rows, followed up — 2026-11-05

After the owner's confirmation the twelve B rows were worked through. The
work is commit `eff2b68cb8dd1850a6f1ba5929aadedc2c419e0a`, merged into
`main` after the review record; **the independence gap this record names is
not changed by it**.

**Four witness gaps were closed, each mutation-verified:**

| B row | The gap | The witness added |
|---|---|---|
| G2.2-4 | deleting `assert_replayable`'s `ATTEMPTING` arm left the whole crash-matrix file green | `test_at2c_an_attempting_operation_is_refused_before_reconciliation_runs` — removing `ATTEMPTING` from the guard reddens it |
| G1-12 | `security_policy.py` had no dedicated witness for "ALLOW cannot change the target" | `test_a_forged_approval_id_cannot_change_the_target` |
| G2.1-5 | a `BEGIN IMMEDIATE` → `BEGIN` mutation left the concurrency test green | `test_a_read_inside_a_unit_already_holds_the_write_lock` |
| G2.1-7 | deleting `env.dispose()` left the persistence tests green | `test_a_restart_disposes_the_old_pool_rather_than_reusing_it` |

**Three checklist references were corrected** — G1-5, G1-10 and G1-11 now
name the nodes that actually redden under the mutation, not the files the
checklist had cited.

**Five rows stay as limitations, not gaps:** G1-6 (a platform premise:
`Path.is_symlink()` on a junction), G2.2-6 (one arm mutated, the other seven
run at baseline only), and G2.3-3/4/5 (one row lists several mechanisms; a
single mutation cannot cover all of them). No witness was manufactured for
these.

**The coordinator's verification.** The four files pass together (**53
passed**); the witness ledger over the merge is `LOST — none` with **4 test
functions added**; `ruff`, `ruff format` and `mypy` (397 source files) are
green. The coordinator re-ran the `ATTEMPTING` mutation personally: the new
witness reddens and the restored file turns green. The other three
mutations were verified in the session that wrote the witnesses.

---

## 6. The independent session's review — 2026-11-05

Under the owner's decision of 2026-11-05, an **independent agent session**
(no project memory, no part in building the work, given no account of the
earlier packet) re-ran the checklist itself. Its packet lives outside the
repository at `E:\labcairn-local\G1-G2-independent-review\`
(`REVIEW-SHEET.md`, `SUMMARY.md`, and the per-row mutation journals). **No
human being performed this reading.**

| | Independent reading | Owner-confirmed reading |
|---|---|---|
| A | **19** | 21 |
| B | **14** | 12 |
| C | **0** | 0 |
| D | **0** | 0 |

- The independent reading's reviewed commit is
  `1d328fd97f2b61d02aab396a8322e8fc8cc084ad`; the later `main` carries the
  four new B-row witnesses and three citation corrections named in §5. A
  row marked B on the earlier tree is not a claim that it is still unfixed.
- **All 33 rows have evidence, with no C and no D.** Every product claim
  the independent reader could exercise held, and every B names a witness,
  citation or mutation-coverage problem rather than a failed property.
- **Windows only.** POSIX-only witnesses are NOT MEASURED; the checklist's
  two-platform requirement remains unmet on this machine.
- The independent session's clean whole-suite run was stopped when it was
  found running concurrently with the baseline harness — two whole-suite
  runs must not share this machine. Its partial result is **not** counted
  as evidence; the row-level mutations are the evidence.

**What this discharges.** The board's independence rule asks for a review
at a named commit by a party that neither wrote the fixes nor dispatched
them. Under the owner's 2026-11-05 decision an independent agent session may
stand in for a human reader, and this review was such a session's: it had
no project memory and took no part in the work. **§0's `not the party that
dispatched them` clause is therefore satisfied by this review**, with the
session's identity recorded rather than a person's. The owner-confirmed
reading of §1 remains a separate act by the dispatching party. Neither
reading is a human being's, and this record does not say otherwise.

**The clean-suite gap.** No uncontaminated whole-suite result backs this
independent review; the row-level mutation evidence and the three exit
demos do. A later run on one quiet machine would supply that number, but
absence of a whole-suite count is not a C or D for any of the 33 rows.
