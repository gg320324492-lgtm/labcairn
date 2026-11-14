# LC-P3-07 — known limits (trial build, 2026-11-14)

**What this is.** The known-limits record work orders §12 §5.6 deliverable 4
pairs with the operator manual. Every entry is a limit the drills *observed*
or a boundary the design states and the run confirmed; a limit nobody observed
is not here. Evidence addresses point into
[LC-P3-07-drill-run-2026-11-14.md](../acceptance/LC-P3-07-drill-run-2026-11-14.md)
and the test modules that carry the witnesses.

## Limits observed by the drills

1. **A killed write leaves its temp file behind on Windows.** A process
   killed while its write handle is open (inside the temp-write window,
   before `os.replace`) leaves the `.lc-write-*.tmp` file on disk with its
   content. This is platform behaviour of an open handle under
   `taskkill /F`, not the product's cleanup path (the `except` cleanup runs
   only when the call itself raises). The destination is never half-written —
   the atomicity contract holds — but the loop's `revisions/` directory can
   hold a leftover temp after a hard crash. *Consequence for the trial:* a
   leftover temp is inert (the marker name is never a destination); a
   following run ignores it. *Owner note:* a sweep of marker-named files at
   loop open would be new semantics (LC-P3-03's ground), so it is recorded
   here, not implemented. Evidence: drill record §interrupted-writes; probe
   `E:\labcairn-local\tmp\p307-probe`.

2. **A locked original refuses the copy as `source_changed`, not as a
   lock-specific error.** The consent's re-hash (`sources_intact`) cannot
   read a file another handle holds exclusively, and reports it as a changed
   source. The operator-visible answer is correct but generic: "the approval
   does not cover this request: source_changed". There is no distinct
   "file in use" wording on this path. Evidence: drill record §locked-files;
   `tests/test_drill_locked_files.py`.

3. **The stop-loss is per-run, not per-session.** Three consecutive failed
   requests end *the run*; a new run starts with a fresh count. The manual's
   "the run stops" is exactly that — a session that starts a new run after a
   stop-loss begins counting again. Evidence:
   `tests/test_drill_provider_faults.py`.

4. **The real-model timeout row stays a named gap.** Per work orders §12 §5.3
   and §14 item 7, the drill matrix's model-timeout row ran against the
   substitute only; the real-model half is an owner addition after
   `LC-P3-06` and is not exercised by this batch. `LC-P3-06`'s own real-half
   record (one 47.0 s completion against the 60 s timeout) is its ticket's
   bounded run, not a drill row here.

## Defects found by the drills and filed, not fixed

- **D-07-01 — the packaged build refuses every `.txt` material.** `task
  create` over a `.txt` corpus refuses `material_incomplete`, every file
  failing with `ExtractionVersionError: cannot read
  ...\_internal\labcairn\material\text.py ... [Errno 2] No such file or
  directory`. The frozen exe embeds the pure-Python product modules, so the
  extraction-version reader's deliberate read-its-own-source check finds no
  file at `__file__`. `.bin`/`other`-kind files are unaffected. *Consequence
  for the trial:* text-material tasks cannot be created on the packaged
  build until `LC-P3-05` fixes the freeze. Owner: `LC-P3-05`. Evidence:
  drill record §5.

## Limits the design states and the run confirmed

5. **The rollback preserves user data; it does not merge.** A rollback
   restores the store from a backup point (SQLite backup API, `mode=ro`) and
   the output area and sources as files. Data written after the backup point
   is *kept* (the output area is not the store), and the record names it with
   its digest. A rollback never rewrites history: a confirmed publication
   stays confirmed. Evidence: `tests/test_drill_backup_rollback.py`.

6. **A naive file copy of a live WAL store is a torn copy.** The drill
   reproduced the difference: the backup-API copy carried the
   uncheckpointed writes; a `shutil.copy2` of the live database missed them.
   The backup point procedure therefore uses the backup API with the source
   opened `mode=ro`, before any writes. Evidence:
   `tests/test_drill_backup_rollback.py::test_a_backup_of_a_live_wal_writer…`.

7. **The reconcile hash is not in the store.** `resolve_abandoned` needs the
   content hash the operation predicted, stated by a human; the refusal
   message says so and prints the command. An operator cannot answer the
   question from the store alone — that is the design, not a defect
   (recovery must not replan). Evidence:
   `tests/test_drill_known_errors_recovery.py`.

8. **Diagnostics refusal is all-or-nothing.** A package whose any text field
   fails the de-identification checks is refused whole — there is no
   "ship the clean fields" path, by design (a caller that ships around the
   refusal is a caller that has learned to leak). The operator sees
   "diagnostics refused" naming the check. Evidence:
   `tests/test_diagnostics_package.py`.

## Deferred, with owners

9. **Signing and distribution** — deferred behind `W28`; owner decision
   (work orders §12 §5.3).
10. **Installer upgrade/uninstall mechanics** — `LC-P3-05`'s deliverable;
    this batch drilled the preservation semantics the mechanism must satisfy,
    on the unpacked tree. The installed-from-`Setup.exe` pass belongs to
    `LC-P3-05`'s own drill record.
11. **Real advisor sample and the trial itself** — `LC-P3-08`; owner-gated.
