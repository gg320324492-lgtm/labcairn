# LabCairn operator manual — trial build

**Status:** filled from the LC-P3-07 drill run on the packaged build
(`win-unpacked` tree of `dist3/LabCairn Setup 0.0.0.exe`, backend frozen exe
under `resources/backend/labcairn/`). The drill evidence is
[../acceptance/LC-P3-07-drill-run-2026-11-14.md](../acceptance/LC-P3-07-drill-run-2026-11-14.md);
the known limits live beside it in
[LC-P3-07-known-limits-2026-11-14.md](LC-P3-07-known-limits-2026-11-14.md).

## 0. About this manual

- **Who it is for:** the trial participant running the revision loop, and the
  person supporting them (work orders §12 §5.4; the trial itself is
  `LC-P3-08`).
- **What it is not:** not the architecture (`docs/ARCHITECTURE.md`), not the
  threat model (`docs/THREAT-MODEL.md`).
- **Build identity:** `LC-P3-05`'s packaged build, frozen backend
  (`labcairn.exe` under `resources/backend/`), launched by the package's
  `LabCairn.exe` shell. The five-item identity line (commit, package hash, OS
  and Word versions) is recorded in the drill record; this manual describes
  that build's observed behaviour, from the drills named beside each row.

## 1. Getting the build onto the machine

The installer and its uninstall/rollback **mechanism** are `LC-P3-05`'s
deliverable; their preservation claims are drilled in
[LC-P3-07-drill-run-2026-11-14.md](../acceptance/LC-P3-07-drill-run-2026-11-14.md)
§backup. What the operator needs:

- Install from `LabCairn Setup 0.0.0.exe`. The package carries no Python; the
  backend is the frozen `labcairn.exe` the shell spawns exactly as its
  supervisor does.
- The workspace lands where the package's `shell-env.json` names it
  (`LabCairn-workspace` beside the install). The first run initialises it;
  the product refuses a directory with no `workspace.json`
  (`workspace_not_initialised`).
- The backend needs `PYDANTIC_DISABLE_PLUGINS=1` in its environment — the
  shell's supervisor sets it; a hand-launched backend must set it too, or it
  dies at start-up.

## 2. The loop, start to finish

One revision loop, as the operator performs it. Each step names the
confirmation the operator sees; the consent questions are shown in the
operator's terms.

| Step | What you do | What you see |
|---|---|---|
| 2.1 pick the source | Point the task at a file inside a configured source root. Source roots are read-only by construction: the read-only door (`SourceMaterial.read_permitted`) applies the policy to the file and keeps the original untouched. | The task's source list shows the file; its content hash is printed by `labcairn sources inspect`. |
| 2.2 the import | Open the revision loop (`open_loop`). | An import receipt at `revisions/<receipt_id>/import-receipt.json` names the original's SHA-256 — the hash every later check compares against. |
| 2.3 the copy, and its consent | Ask for the copy (`request_loop_approval`, stage `revision-copy`) and grant it. | One approval, bound to the original's bytes at the ask (the `bound_sources` hash). The grant covers one write; a second write asks again. |
| 2.4 edit | Edit the copy at `revisions/<receipt_id>/copy.bin` in the task output area. | The original is never opened for writing; the copy is the edit surface. |
| 2.5 publish, and its consent | Ask for the publication (`stage_name` `revision-publication`) and grant it; publish (`publish_revision`). | A publication receipt derived from both the original's and the import's hashes. A second publication of the same loop is refused by name (`loop_already_published`) with the remedy: import the new bytes as a new loop. |
| 2.6 the review half | Opinions, suggestions, decisions and handover through the binding surface (`labcairn.papers.binding`). | Each step is a ledger row; the chain is the record. |

## 3. When something goes wrong — what the build says, and what to do

Organised by what you see, keyed to the five drill classes. Each row's
behaviour was drilled on the packaged build; the evidence address is in the
drill record.

| What you see | What it means | What to do |
|---|---|---|
| the run stopped mid-write / a file is half there | Should not happen by design: writes go to a temp file in the destination's own directory, are flushed and `fsync`-ed, then `os.replace` moves them into place atomically. The drill killed the process inside the write windows; the destination was never half-written. | If you ever see a half-written *destination*, that is a defect: report it with the file path. A leftover temp file (a `.lc-write-*.tmp` name in the loop's `revisions/` directory) is the crash's own leftover, not an output; a following run ignores it, and it can be deleted. |
| "file in use" / a lock | A source the OS will not let anyone read stops the copy before any write: the consent's own re-hash cannot read the original, so the approval is refused (`source_changed`) and the write primitive is never reached. The loop's import receipt stays in place. | Release the lock and re-run the copy stage. The loop does not need re-importing. |
| the network went out mid-request | The failure arrives typed (`PROVIDER_TRANSIENT` / `TIMEOUT`), classified by the provider layer, and counts as a *failure* — not a refusal. Local results already confirmed stay confirmed; the run's record holds counts, never the provider's error text. | Retry when the route is back. The stop-loss counts three consecutive failures; after the third the run stops rather than spending further budget. |
| the model took too long | A request that exceeds the configured timeout is recorded as a failure; three consecutive ones end the run (`StopLossTriggeredError`). Nothing is published from a timed-out suggestion. | Re-run the case when the provider is responsive. The run's record shows the counts; the stop was the ceiling working. |
| a refusal naming itself (`cross_project_access`, `path_refused`, `approval_refused`, `loop_already_published`, `source_drifted`, …) | Each is a design refusal with its reason in the message. | Read the named remedy. `loop_already_published` → import the new bytes as a new loop. `source_drifted` → the original moved under the loop; re-verify with `labcairn sources inspect` before deciding. |
| "a crash left operations whose outcome the record cannot state" | The recovery path: the message names the operation and prints the one command that answers it — `labcairn task reconcile <operation_id> --expected-sha256 <hash>`. The hash is not in the store; a human states the bytes the operation was predicted to write. | Run the printed command with the hash you expect (`labcairn sources inspect` prints a material's content hash). A matching hash confirms the effect landed; a mismatching one is a conflict that stays blocked for you to decide. |
| task create refuses every text file with `ExtractionVersionError: cannot read ...\_internal\labcairn\material\text.py ... No such file or directory` | **Known defect of this packaged build** (D-07-01, filed to `LC-P3-05`): the frozen backend cannot read its own extraction-adapter source to version the text adapter, so every `.txt`/text material is reported unreadable. `.bin` and other non-text files are unaffected. | Do not retry — it is not a transient. Report it; a build with the fix will create the task normally. |
| a rollback was run | The rollback restores the store from a backup taken with SQLite's backup API (`mode=ro`), and the output area and sources are restored as files. | After a rollback, the published revisions and the originals are byte-identical to the backup point (drilled by digest comparison). Anything written after the backup point is kept — the output area is not the store — and is named in the rollback record. |

## 4. Getting diagnostics out

- Collect the package with the diagnostics surface
  (`labcairn.diagnostics.collect_diagnostics`; the trial build's window
  action wraps it). The package carries: build identity (version, schema
  revision, platform), the task's id only, operation states and transitions,
  typed provider failures, bounded-run counts, capability probe verdicts,
  credential *fingerprints* (never values), output-area file facts
  (workspace-relative paths, hashes, sizes), and event names with UTC
  moments.
- **What is not in it — your material is not in it.** The package carries no
  source text, no excerpt, no rendered prompt, no credential value, no
  provider's raw error text, and no absolute path into a source root. This is
  proven, not promised: the package is minted only by a collector that
  verifies every text field against the material's runs and the registered
  secrets before the package exists, and a field that fails verification
  refuses the whole package (you see "diagnostics refused" naming the check —
  not a package with blanked fields).
- If collection is refused, the refusal names the check that failed. Do not
  try to work around it; report the refusal itself to your supporter.
