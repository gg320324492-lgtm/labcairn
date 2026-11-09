# LC-P3-03 — project authorisation and versioned writes: substitute run

**Date:** 2026-11-10.
**Branch:** `claude/cool-vaughan-fadf22` (worktree
`E:\LabCairn\.claude\worktrees\cool-vaughan-fadf22`; the worktree's own path
is named here because this is a local run record, not a public-boundary
document).
**Base:** `26f816b2ecaf03a3d62b914d685edd4f54e0356b`.
**Head of this work:** `7f1bd6c954279ef62dc74dfeede6af2859ed5a00`.
**Status:** local evidence only. No push, no pull request, no CI run. The
board row is the commander's to move; this record does not claim `PASS` for
Phase 3 G2.
**Substitute-first:** all-synthetic by nature (`PHASE_3-work-orders.md` §8
1.8). No provider call, no credential, no spend, no advisor material, no COM
or UI automation. Every byte in every witness is authored in the test tree.

## 1. What ran, and on which machine

| What | Where | How measured |
|---|---|---|
| The whole loop, end to end | Windows 11 Pro 10.0.26300, CPython 3.12, local venv at `E:\LabCairn\.venv` | `probe_loop.py` in `E:\labcairn-local\tmp\p303-probe` (outside the repository), with `PYTHONPATH` pointed at this worktree's `src`. Printed `PROBE DONE` after import, copy, publication, duplicate refusal and stale-approval refusal. |
| 17 witnesses (two new files) | same machine, same interpreter | `python -m pytest tests/test_revision_loop.py tests/test_revision_loop_refusals.py --basetemp=E:\labcairn-local\tmp\p303-tests\bt6` → **17 passed**. Repeated with `bt7` and `bt8` while the code was being fixed. |
| Four counter-mutations | same machine | `run_mutations.py` in `E:\labcairn-local\tmp\p303-mutations`; each patch applied to the product module, one witness run, module restored. All four ended `RED (witness holds)`; see §4. |
| Related regressions (11 files, incl. shard coverage) | same machine | **256 passed, 1 failed** at `bt9`: `test_application_layer.py`'s store-reader allowlist named the new module. The allowlist was extended with a stated reason and that file re-run alone → **110 passed** at `bt10`. |
| Whose numbers these are | — | Every number above and below is **locally measured on this machine**, not a runner number. `TEMP`, `TMP`, `TMPDIR` and `MPLCONFIGDIR` all pointed under `E:\labcairn-local\tmp`; every `--basetemp` was a distinct directory outside the repository. Status was read from each command's own exit code, never from a pipe. |
| Static gates | same machine | `ruff check .` → All checks passed; `ruff format --check .` → 467 files already formatted; `mypy --strict src tests` → Success, 418 source files. |
| Public-boundary witnesses | same machine | 193 passed, 2 failed at `bt11`. One failure was a fresh `I001` in a new test (fixed); the other was `test_wheel_installs_clean_and_imports`, whose wheel was shadowed by the worktree's own `PYTHONPATH` — re-run without that variable at `bt13` → **1 passed**. This is the editable-install shadow, not a product failure. |
| Witness ledger | same machine | `python scripts/witness_ledger.py 26f816b2… 7f1bd6c9…` → **LOST -- none**, **ADDED -- 17**. |

The end-to-end probe's printed facts, in order: the import receipt's
`original_sha256` equalled the real file's SHA-256; the manifest existed on
disk; the copy approval's `bound_sources` carried the original's hash on the
row; the copy's bytes equalled the original's; the publication's bytes equalled
the edited bytes; the original's bytes and hash were unchanged after publishing;
the publication receipt carried two derivations (the original's hash and the
import receipt's hash); the duplicate publication was refused with
`loop_already_published`; and after the original was overwritten with real
bytes, the copy was refused with `approval_refused: source_changed` and **the
copy file did not exist**. `PROBE DONE`.

## 2. What landed

`src/labcairn/application/revision_loop.py` binds the pieces the gap register
named, without redesigning any of them:

* **import receipt** — `open_loop` reads one original through
  `SourceMaterial.read_permitted` (the read-only door and the policy's
  verdict), records it in the ledger with `ingest_bytes`/`put_source`, binds it
  to the task, and writes a manifest plus a `MANIFEST` `ArtifactReceipt` whose
  `MATERIAL_FILE` derivation carries the original's content hash.
* **independent-copy transaction** — `stage_copy` spends one approval and
  writes the original's bytes into the task output area through
  `TaskOutputArea.write` (the product's single atomic write point). The copy is
  a different real path from the original, and its hash is asserted equal to
  the import receipt's.
* **content hash** — `verify_original` re-hashes the original at the copy and
  the publication, and refuses `source_drifted` when the bytes moved. The
  receipt, the approval's bound source, the copy and the publication's
  derivation all compare against that one hash.
* **publication receipt** — `publish_revision` spends a second approval,
  writes the edited bytes, and records an `ArtifactReceipt` derived from both
  the original's hash and the import receipt's hash.
* **recovery path** — an operation left `ATTEMPTING` (the state a crash before
  the confirming transaction leaves) enters `UNCERTAIN` through
  `reconcile_abandoned` and is resolved by `resolve_abandoned`'s read-only
  probe. The drill asserts `CONFIRMED`, `replay_permitted is False`, one
  artefact row for the publication id, and the edited bytes still on disk. A
  differing file at the publication key stays blocked and is not clobbered.

Three additive seams, none a redesign:

1. `security.approval.make_approval` now mints `Approval.bound_sources`. The
   frozen contract has carried the field since LC-P2-02 and the spend re-hashes
   whatever the row holds, but **nothing minted it**: every approval the layer
   previously granted covered no source file. `ApprovalRequest.bound_sources`
   states the binding at the ask, and `grant_approval` copies it into the grant
   so the in-memory and stored ledgers compare the same evidence.
2. `consent.consume` accepts a `resolve_source`. Its default resolves a bound
   source against the write target's root — correct for effects that read and
   write the same root, wrong for a copy *from* a source root *into* the output
   area. Without the explicit resolver, the spend would hash a file that is
   not the original and report `SOURCE_CHANGED` for material that never moved.
   `run_stage` passes it through.
3. The import reuses `ingest_bytes`' location-derived `SourceId`. A UUID is not
   a `SourceId`, and `sources.relative_path` is UNIQUE because material
   belongs to the workspace and outlives tasks. A second loop over the same
   file therefore imports the same material, witnessed.

Two refusal names were added to `ApplicationRefusal`:
`cross_project_access` and `loop_already_published`.

## 3. The four refusals, each from real file operations

| Class | The real setup | What the witness asserts |
|---|---|---|
| **cross-project access** | A second task is created over the same selected root and a real `foreign.bin` is written in that task's output directory. A declared `../output/<other-task-id>/foreign.bin` resolves there. | `cross_project_access` before any file is read or written; `WriteSpy.calls == []`; the foreign bytes and the loop's own original are unchanged. The classification uses the **real resolved path** against the workspace's `output/` tree, because canonicalisation attributes another task's output directory to the enclosing workspace root, not to this task's output root. |
| **path escape** | A real file outside the selected workspace (`outside-the-workspace.bin`) and a real file inside the workspace but outside the source root (`loose.bin`). | `path_refused` (`outside_every_root` for the first; wrong-root for the second), no write primitive reached, both files byte-for-byte unchanged. |
| **stale approval** | The approval's window is still open; **the file moves**. Real bytes are written over the original after the grant (copy witness) and after the import (publication witness). | `approval_refused` with ADR-0003's own `source_changed`; no write primitive reached; the copy/publication file does not exist afterwards. The grant's `bound_sources` hash is asserted against the import receipt's before the mutation. |
| **duplicate requests** | One copy approval is spent twice; then a **fresh** publication approval is granted for a second publication under an id whose receipt and bytes are already on disk. | `approval_refused: consumed` for the first; `loop_already_published` for the second, before the write. The spy is empty, the first publication's bytes and hash hold, and exactly one artefact row carries that publication id. |

Every row's second half — "before any file is touched" — is carried by the
`WriteSpy` in `tests/revision_loop_support.py`, which patches
`builtins.open`, `os.open`, `os.replace`, `os.rename`, `os.remove`,
`os.unlink`, `os.mkdir`, `os.makedirs` and the `shutil` copy/move primitives.
A read (`open(path, "rb")`) is not counted: the loop hashes originals through
that door, and a spy that counted reads would make every witness vacuously
red.

## 4. Counter-mutations

Each mutation is a **semantic** change to the product module; each was applied,
one witness run, and the module restored. A mutation that leaves its witness
green tested nothing.

| Class | Mutation | Witness result |
|---|---|---|
| cross-project access | Name the other-project refusal `path_refused` instead of `cross_project_access` | RED: `assert PATH_REFUSED is CROSS_PROJECT_ACCESS` fails. |
| path escape | Reclassify the canonicaliser's escape refusal as `arguments_invalid` | RED: `assert ARGUMENTS_INVALID is PATH_REFUSED` fails. |
| stale approval | Bind the approval to `"0" * 64` instead of the original's hash | RED: the grant's bound hash no longer equals the import receipt's. |
| duplicate requests | Make the receipt lookup see no prior publication (`landed = ()`) | RED: the second publication completes instead of refusing. |

Earlier attempts at the first and fourth mutations were **not** effective (one
changed a condition that the branch did not decide; one produced a
`SyntaxError`; one inverted the condition and reddened the setup rather than
the property). Those were discarded and the mutations above re-run; the record
states this because a red run is not by itself evidence that the mutation was
effective.

## 5. ADR-0021's temporary independent-copy mechanism (§14 item 6)

**Absorbed, with its temporary code left in place and named.** The product
mechanism is this ticket's `stage_copy`: the independent copy lives in the task
output area, is written by `TaskOutputArea.write` (the one atomic write point),
is authorised by an approval bound to the original's hash, and is asserted
byte-identical to the original. `src/labcairn/editing/evidence.py` — the
labelled temporary mechanism that copies a manuscript to a caller-named
directory for the fidelity experiment — is **not** wired into the product
loop, is not deleted and is not presented as the product mechanism. Its own
docstring and ADR-0021 still say `temporary`. LC-P3-02's substitute-run
outputs stay where they are; the experiment's evidence writer keeps its job.
Per the owner's 2026-11-09 answer, **ADR-0021's text was not edited**; its
wording is settled at that ADR's final adoption, which §5.9 binds to the real
sample.

## 6. Measured gaps (named, not assumed away)

1. **No runner number.** All 17 witnesses, the 256+1 regression set, the
   second 110-test run, the static gates and the four mutations were measured
   on this Windows machine. No CI run was started (`CLAUDE.md`). The two new
   files are registered in `.github/ci-shards.json` with costs of `0.0` on
   both platforms — a placeholder that says "not measured", not a timing.
   `tests/test_ci_shard_coverage.py`'s freshness witness is **expected red**
   until the batch's own runner run and `remeasure_shards.py <run-id>` supply
   real per-file costs and a new `measured_at`. This is the G1 precedent, not
   a skipped check.
2. **The recovery drill is a state injection, not a process kill.** It puts a
   committed `CONFIRMED` operation row back to `ATTEMPTING` through the store's
   own session, then runs the real recovery pass and probe. That is the exact
   state a crash before the confirming transaction leaves, but it does not
   kill a process. The subprocess crash matrix belongs to
   `tests/test_recovery_crash_matrix.py`; a loop-specific kill-and-restart
   drill is not measured here.
3. **One approval per effect; no operator UI.** The loop's consents are asked,
   granted and spent programmatically at a fixed moment. The §4.9-style human
   checklist for approving a copy or a publication on an installed build is
   not produced by this ticket; LC-P3-05 owns the shell.
4. **No DOCX fidelity and no comment-to-revision binding.** The loop's
   `edited_bytes` is supplied by the caller. Applying an approved comment to
   the copy and producing the quality report is LC-P3-04's scope; the DOCX
   support matrix remains LC-P3-02's record. The real advisor sample, the WPS
   and Office human reopen checks and ADR-0021's final adoption remain open.
5. **`SourceMaterial.read_permitted` in the copy effect.** The copy reads the
   original a second time inside the authorised effect, through the read-only
   door. The first read (at import) and the second (at copy) are both checked
   by `verify_original`; a source that changes *between* those two reads of a
   single call is a TOCTOU window this ticket does not close. The receipt's
   hash is the authority: a changed original makes the second check refuse.
6. **`WriteSpy` counts standard-library write primitives, not raw syscalls.**
   It is the same patch-the-primitive approach ADR-0003 §C7's
   `test_source_root_is_read_only_before_any_syscall` uses. A caller that
   reached a platform API outside those primitives is not covered.
7. **The loop's own import is not approval-gated.** It is a read of permitted
   material and a write of the loop's manifest into the task output area;
   the two *effects* (copy and publication) are gated. Whether import itself
   should ask a human is a product decision not made in §8.
8. **Board status.** `PHASE_3-work-orders.md` §1 still rows LC-P3-03 as
   `NOT STARTED`. This record is evidence, not a board move; the row moves
   in the same commit as the verdict that moves it.

## 7. Where each claim is witnessed

| Claim | File |
|---|---|
| receipt/copy/publication/hash loop, one-material reuse, read-only guard, probe recovery, conflict stays blocked | `tests/test_revision_loop.py` (9 witnesses) |
| four refusal classes, before-touch spies, consumed and drifted approvals, duplicate publication | `tests/test_revision_loop_refusals.py` (8 witnesses) |
| real-file setup, a second task's output, WriteSpy, fixed clock | `tests/revision_loop_support.py` (support, not a test) |
| four mutations | `E:\labcairn-local\tmp\p303-mutations\run_mutations.py` (outside the tree; this record is its evidence) |
| end-to-end substitute run | `E:\labcairn-local\tmp\p303-probe\probe_loop.py` (outside the tree) |

No Chinese corpus text, no owner-side absolute workspace path and no runner
tally enters this file; the only path outside the public boundary named here
is this worktree's own location and the two scratch directories, in the
machine-column sense §3 rule 6 ("A measurement says where it ran") asks for.
