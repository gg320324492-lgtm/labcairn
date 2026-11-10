# LC-P3-07 — backup points and rollback semantics (design)

> **DESIGN — not a deliverable until run on the installed build.**
> `LC-P3-07` stays `BLOCKED` on `LC-P3-05`'s installed build (work orders
> §12 decision 2, 2026-11-10). This is the substitute-first design of §12
> §5.6 deliverable 3 (*"the backup and rollback drill, matching execution plan
> §4's demand that a rollback preserve user data"*) and of its witness design.
> No drill was run; every claim about existing behaviour is anchored to the
> module or record named beside it, and every installed-build question is
> marked **[placeholder]**.

Companion designs: [drill matrix](LC-P3-07-drill-matrix-design.md),
[diagnostics](LC-P3-07-diagnostics-design.md),
[manual skeleton](LC-P3-07-manual-skeleton.md). Work order:
[PHASE_3-work-orders.md](PHASE_3-work-orders.md) §12.

## 1. The row this design drills, and the seam against `LC-P3-05`

Execution plan §4's "Distribution and review" row (quoted at §12 §5.7), the
half 07 owns: *"A clean supported Windows environment proves install and run,
and **a rollback preserves user data**."*

The seam, stated so the two tickets do not drill each other's ground:

| Owned by `LC-P3-05` | Owned by `LC-P3-07` |
|---|---|
| the installer's own upgrade drill, uninstall, and rollback **mechanism** (its §3 row: *"install, launch, upgrade drill, uninstall and rollback"*; ADR-0023 — [../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md](../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md)) | the **semantics** the mechanism must satisfy: *preserves user data* — measured, with the measurement named (§4 below); and the backup-point design the mechanism restores from |
| the mechanism exists on a clean Windows environment | the mechanism is *fault-drilled* under §12's five classes — a rollback attempted while a locked file is still locked, a backup taken while a publication is mid-flight, a rollback interrupted like any other write |

§12 §5.4 keeps 07 from owning the installer and `src/labcairn/application/`'s
semantics: this document designs the drill and the claims, and a drill that
finds the mechanism failing files the defect against `LC-P3-05` (installer) or
`LC-P3-03` (loop semantics) — it does not repair either here (§12 §5.2).

## 2. What "rollback preserves user data" means, precisely

The claim has to be checkable sentence by sentence, or the drill will observe
only that "nothing obviously broke". The design states three user-data
classes and what preservation means for each:

1. **The ledger (the store).** The event-and-permission model
   ([ADR-0003](../adr/ADR-0003-event-and-permission-model.md)) makes the store
   the record of what happened; a rollback that rewrites history is not a
   rollback. Preservation means: every event, approval, artefact row and
   version-graph row present before the rollback is present after, with the
   same digests — asserted by digest comparison (§4), not by eyeballing a row
   count.
2. **The task output area.** The published revisions *are* user data — a
   publication receipt is an immutable fact in this product (the loop refuses
   its own duplicate by name, `loop_already_published` in
   `src/labcairn/application/refusal.py`; §12 §5.3 keeps 07 from adding
   refusal semantics). Preservation means the published bytes are byte-identical
   after the rollback: each file's `content_sha256` from its `WriteReceipt` /
   `ArtifactReceipt` row re-hashed and compared.
3. **The source roots.** The originals are protected by the read-only door
   (`SourceMaterial.read_permitted` in `labcairn.workspace.readonly`) on the
   product side and by "the original is intact" on the claim side (execution
   plan §4's "Cancel, retry and recovery" row, quoted at §12 §5.7). A rollback
   must not move them — the drill re-verifies the original's hash against the
   import receipt, which is the public surface `verify_original` in
   `labcairn.application.revision_loop` already exists to run.

A rollback that *silently discards* writes made after the restore point is a
defect of a different kind, so the design states the rule: **data written
after the backup point is either kept, or its loss is named in the record
with its digests.** "Quietly gone" is a failed drill.

## 3. Backup points: when, and of what

The store's shape fixes what a backup even is. The store is one SQLite
database in WAL mode (`PRAGMA journal_mode=WAL` in `src/labcairn/db/session.py`
— set deliberately, with `busy_timeout` ordered *before* it, for exactly the
reason that matters here: a backup taken while a writer is live must not read a
torn WAL). The landed precedent for backing one up is already in the tree's
records: **SQLite's `backup` API with the source opened `mode=ro`**, taken
before any writes, with the copy's alembic revision and every table's row
count checked against the source's — the rehearsal-store method of
[../acceptance/LC-P2-08-batch9-version-graph.md](../acceptance/LC-P2-08-batch9-version-graph.md)
§2 and
[../acceptance/LC-P2-08-batch10-version-graph.md](../acceptance/LC-P2-08-batch10-version-graph.md)
§2, each anchored to its own run's store digests. The design decision: 07's
backup drill uses **that same route** (a copy that runs while the app may write
is a copy of a torn state), not a file-level copy of a live WAL database.

The candidate backup-point schedule (to be confirmed against the installed
build's lifecycle — **[placeholder]** which of these the shell can actually
trigger):

| Point | Trigger | What is backed up | Why this point |
|---|---|---|---|
| **pre-upgrade** | the installer's upgrade step (`LC-P3-05`'s mechanism) | the store, via `backup`/`mode=ro`; the output area is *not* replaced by an upgrade and must stay byte-identical | the rollback half of §4's row is *this* rollback; the drill verifies it against §2's three classes |
| **pre-trial** | before an advisor-to-student-to-advisor loop starts (`LC-P3-08`'s trial) | store + output area (file copy — output-area files are already atomic units per `TaskOutputArea.write`: temp name, `fsync`, same-volume `os.replace`) | the trial is the first time a *person's* real material is in the store; a trial disaster must be restorable without losing what the loop already published |
| **mid-loop — deliberately none** | — | — | the publication transaction *is* the recovery mechanism for an interrupted loop (reconcile/resolve — §5); a backup per loop stage would multiply states the loop's own receipts already pin. The drill proves this absence is safe rather than assuming it. |

A backup point is **outside the repository and outside the workspace's source
roots** in any rehearsal (the project's own temp/workspace rule: a workspace
inside the checkout makes the run depend on the tree it runs in). The trial's
own location is the owner's; §12 §5.5 keeps fault injection from needing real
material — every substitute-half backup drill runs on synthetic material.

## 4. The witness design: "preserves user data" as a measurable comparison

The landed precedent for this exact witness shape is in the records named in
§3: the batch-9 and batch-10 rehearsals each state *"the real store's sha256
remained … before and after the run"* alongside the copy's own digest and
`integrity_check = ok`. That is the pattern 07's drill witnesses copy — a
before/after digest comparison the record itself prints:

1. **Snapshot before the rollback:** the store file's sha256, the alembic
   revision read from the store, per-table row counts, and the output area's
   set of `(relative_key, content_sha256)` pairs from the receipts.
2. **Snapshot after the rollback:** the same six kinds of value.
3. **Assert:** equal sets, equal digests, `integrity_check = ok` on the
   restored store; any post-backup-point data that did not survive is *named*
   in the record with its digest (or the drill fails).

Counter-mutation family (the drill-matrix design §3's policy applies — at
least one per family, semantic, restored from `HEAD`, ineffective attempts
recorded as discarded):

| Mutation target | Mutation | The witness that must go red |
|---|---|---|
| the rollback rehearsal's restore step | let the restore overwrite an output-area file that post-dates the backup point (the "quietly gone" defect §2 names) | the before/after output-area digest comparison — it must name the file that changed |
| the snapshot itself | compare row counts only, not digests (the counts stay equal while one row's content changed) | the digest-comparison witness — red, because equal counts hid a changed digest. This mutation is *about the witness* in the project's own sense: a check that cannot see the defect is not a witness |
| the store check | restore a copy whose WAL was never settled and read it with a naive reader | the settled-WAL / `integrity_check` step goes red — the `backup`-API-before-writes rule earns its place exactly here |

The last row is the family's load-bearing one: it is the same fact the tree
already learned the hard way when a copy of a live store and a copy of a
settled store differ by the size of the uncheckpointed writes.

## 5. The relationship to `revision_loop`'s recovery path

Three operations the design keeps apart, because the drill's job is to show
the product keeps them apart:

| | reconcile / resolve | rollback |
|---|---|---|
| Question answered | *"did the interrupted operation's effect happen?"* | *"put the whole workspace back at a known point."* |
| Mechanism | read-only probe → state transition. `RecoveryCoordinator.reconcile` in `src/labcairn/recovery/reconciliation.py`; the operator's surface is `resolve_abandoned` in `src/labcairn/application/recovery.py` (CLI: `labcairn task reconcile <operation_id> --expected-sha256 <hash>`), whose predecessor `describe_abandoned` names the operations *and* the one command that answers them | restore store + output area from a backup point (§3) |
| What it may not do | **replan.** Replay is refused on purpose: *"re-running would plan a second operation for work that may already have happened"* (`describe_abandoned`'s own words); and the hash it needs is *not in the store, so this cannot be answered automatically* — a human states the predicted content hash | **rewrite history.** §2's three classes; a confirmed publication stays confirmed (`loop_already_published` guards it) |
| Where a backup point enters | **nowhere automatic.** A backup is another information source for the manual check resolve can hand to a person — the drill may show an operator answering `describe_abandoned`'s open question from a pre-trial snapshot's digests — but `resolve_abandoned` itself reads the store and the stated hash, not a backup file. Making it read backups would be new semantics, i.e. `LC-P3-03`'s ground (§12 §5.3). | — |

The `LC-P3-03` record
([../acceptance/LC-P3-03-revision-loop-2026-11-10.md](../acceptance/LC-P3-03-revision-loop-2026-11-10.md))
already ran the *recovery* drill end-to-end on a substitute
(`reconcile_abandoned` / `resolve_abandoned` in `tests/test_revision_loop.py`);
07's contribution at this seam is running the same question **with a backup
point present, on the installed build**, and showing that resolve's answer does
not silently become a restore.

## 6. Open placeholders for the run

- **[placeholder]** which lifecycle events the installed shell can hook
  (pre-upgrade / pre-trial buttons vs. operator-run CLI steps);
- **[placeholder]** where the trial's backups live and who holds them (owner /
  trial logistics — `LC-P3-08` §13's decision area, not this design's);
- **[placeholder]** the installed build's store location per user profile and
  whether an uninstall touches it — `LC-P3-05`'s uninstall drill answers
  whether uninstall counts as a rollback that must preserve user data, and 07's
  drill verifies whatever the installer claims;
- **[placeholder]** backup size and duration measured on a store of trial
  scale (the 2026-11-05 records measured 66–68 MB pilot stores; a trial store
  is different, and the number must come from the drill, not from those
  records).
