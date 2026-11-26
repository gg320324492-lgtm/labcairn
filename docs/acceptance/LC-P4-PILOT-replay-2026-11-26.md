# LC-P4-PILOT — replaying the round on the pilot copy against the tree that closes the two gaps

**Ticket:** LC-P4-PILOT (the replay, on the imported copy, against the tree that closes gaps 1 and 2)
**Date:** 2026-11-27.
**Tree:** `9d3d4a77d67b7865ccacdfc0066f6fe205cd2fba` (worktree
`stoic-lichterman-987a04`), Windows 11 Pro (10.0.26300 x64, AMD64),
Python 3.12.13.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Workspace:** `E:/labcairn-local/pilot-ws` — the pilot copy the first round
ran on. **Before this replay** the store was at revision `0032`, held
`10,305` events, and its current task was
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1` ("Pilot revision round 2
(desensitised copy pilot-paper-002)"); the material is source
`src-0ac499ea4d3a7d82`, `pilot-paper-002.docx`, sha256
`04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`,
8,805,237 bytes. **After this replay** the store is at revision `0034`,
holds `10,401` events, and the same task and source ids are unchanged.
**Material:** the same source row, `src-0ac499ea4d3a7d82`; the replay also
read the comment chain under `proj-pilot-2` (issue key
`iss-c2-<redacted>-15`, version `ver-pilot2-<redacted>`), whose material is
`corpus2-<redacted>.docx` under root `source:0`.

**Those three identifiers are redacted, and the redaction is the point.**
The issue key, the version id and the file name are the workspace's own
labels for the second corpus's material, and **a label that carries a
person's name is material too** — the rule this repository works by is
that the tree keeps desensitised metadata, digests, counts and ids, never
the material's own wording and never the names of the people whose
material it is. The corpus and the root are still there, so a reader can
find the row; the name is not.
**Policy:** digest `2f0d7827d44c4fa81577e871f856ceadf33f12443c718e8727d4292c993d4da6`
(unchanged from the first round).

**What is claimed here.** The first round's §6 listed four places where the
product's own bookkeeping stopped; the first two — **a refusal left no
event**, and **a stage stayed `blocked` / a run stayed `running` after its
approval was consumed and its request answered** — are closed in this tree
(migration 0033, `refusal_recorded`, and the operation/stage/run closure).
This record **replays the round on the pilot copy** against this tree and
measures what the log now says: the refusal is in the log, and the stage
and the run close. The commands, ids, digests, counts and timings below
were measured on this tree against this workspace.

**What is not claimed.** That a real model request was made — **none was**;
the consent-gate run used an injected `send` that returns a fixed
invocation without reaching the wire, so the gate, the approval, the
exchange record and the closure are the product's, but the answer is not a
model's. That the advisor loop ran — the copy carries no comments under the
first round's key, and the replay's successful run used a different
project's chain. That the CLI carries a model request of its own — it does
not, and §4 says why.

**The boundary this record obeys.** Ids, digests, counts, timings and paths.
No sentence of the manuscript, no extracted text, no picture, and no key.
The material's own text (the advisor's comment, the manuscript passage)
never enters this record; where a payload carried it, the record names the
field and not its value.

---

## 1. What was read, before anything ran

`labcairn doctor --json` on the pilot workspace, before the replay: the
workspace is initialised, the database is at revision `0032`, and the
policy is the one the pilot has been running under. The store was read
read-only (`sqlite3.connect("file:…?mode=ro", uri=True)`) for the
before-measurement: `alembic_version` = `0032`, `events` = `10,305`,
`tasks` = 2, `sources` = 199, `stages` = 1,215, `runs` = 1,214,
`operations` = 1,215. The current task is
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1`; the material source row is
`src-0ac499ea4d3a7d82` (`pilot-paper-002.docx`, 8,805,237 bytes,
`readable`).

**The tree is newer than the workspace's schema revision, and the store
migrates when the product opens it.** Migration is applied
programmatically (`from labcairn.db.migrations import upgrade_to_head;
upgrade_to_head(db_path)` — the same function `task create` calls on a
fresh database); the replay ran it explicitly:

```python
from labcairn.db.migrations import upgrade_to_head, current_revision
upgrade_to_head(r"E:\labcairn-local\pilot-ws\labcairn.db")
```

`current_revision` read `0032` before and `0034` after. The migration is
itself part of what was measured: the store moved `0032 → 0033 → 0034`
(migration 0033 rebuilds the events table's four vocabulary CHECK
constraints to admit `refusal_recorded`; 0034 adds `source_removed`), and
the events table's row count was unchanged by the migration itself.

---

## 2. The refusal, replayed

The first round's §3.1 ran the product's only CLI route to a model,
`roles run`, against the pilot copy and it refused with exit code 3 and
`role_comment_not_in_the_chain`, and the day's seventeen events held no
entry for it. The replay runs the same command:

```
labcairn --workspace E:/labcairn-local/pilot-ws roles run \
  --role trajectory --project proj-pilot-002 \
  --issue-key "pilot-paper-002:p[7]" --json
```

It refused again, with the same reason and message and exit code **3**:

```json
{"reason":"role_comment_not_in_the_chain",
 "message":"application refused (role_comment_not_in_the_chain): the chain holds no comment under the key 'pilot-paper-002:p[7]', and a judgement about a comment that is not there is invented"}
```

**And this time the log carries it.** The event read after the refusal:

| seq | type | occurred_at (UTC) | payload (fields, not text) |
|---|---|---|---|
| 74 | `refusal_recorded` | 2026-11-26T16:48:38.790873Z | `reason` = `role_comment_not_in_the_chain`; `asked_for` = `{project: proj-pilot-002, issue_key: pilot-paper-002:p[7], operation: "roles run: request", roles: trajectory}` |

The event's `message` field carries the refusal's own sentence; the record
does not reproduce it beyond the reason. The payload's `asked_for` names
ids, keys and the operation — never the material's text.

A second `roles run` with a real issue key but no material declaration
refused with `role_run_material_mismatch` and was likewise recorded:

| seq | type | occurred_at (UTC) | reason |
|---|---|---|---|
| 75 | `refusal_recorded` | 2026-11-26T16:50:26.121242Z | `role_run_material_mismatch` |

**Gap 1 is closed on the pilot copy:** the refusal that reached only the
exit code and the message in the first round now reaches the event log,
with its reason, its message and the request it was about.

---

## 3. The consent gate, replayed

The first round's §6.2 measured that the approval stage stayed `blocked`
and the run stayed `running` after the approval was consumed and the
request answered. The replay drives one request through the consent gate
and reads whether the stage and the run close.

**The gate, driven from the product's own surfaces.** The ask is
`roles run` without `--approval` (the product writes the question and the
pending approval, spends nothing); the grant is `task approval-grant`; the
spend is `roles run --approval`. Because the CLI's spend reaches the wire
and this window must not make a model request, the spend was driven
through the application layer with an **injected `send`** that returns a
fixed `ModelInvocation` without touching the network — the gate order, the
approval, the transmit check, the exchange record and the closure are the
product's; only the answer is not a model's.

**The ask.** `roles run` against the pilot's `proj-pilot-2` chain (issue
key `iss-c2-<redacted>-15`, version `ver-pilot2-<redacted>`, material
`corpus2-<redacted>.docx` under `source:0`) returned a ticket with a
pending approval:

| field | value |
|---|---|
| approval_id | `01a218c4-5f0c-767d-b288-4198690c3280` |
| asked_at | 2026-11-26T16:50:52.256773Z |
| state | pending (nothing spent, no exchange) |

**The grant.** `task approval-grant 01a218c4-5f0c-767d-b288-4198690c3280`
recorded the human's yes:

| field | value |
|---|---|
| state | `granted` |
| args_digest | `024ca59b4267f8791cc34a0affe291e7cd54de52ac4ab8c94eb8e41ec1f18739` |
| grant_policy_digest | `2f0d7827d44c4fa81577e871f856ceadf33f12443c718e8727d4292c993d4da6` |
| granted_at | 2026-11-26T16:51:26.210292Z |

**The spend, and the closure.** The application-layer run with the
injected `send` and a backend carrying a `external_transmit` grant for
`materials/**` (purpose `transmit`, destination
`https://api.minimax.cn/anthropic`) and a `ProviderCapabilities` declaring
the schema capabilities `OK` spent the approval and returned. The event
chain for that run, read from the log:

| seq | type | occurred_at (UTC) |
|---|---|---|
| 120 | `run_started` | 2026-11-26T16:55:46.616702Z |
| 121 | `stage_entered` | 2026-11-26T16:55:46.616702Z |
| 122 | `operation_awaiting_approval` | 2026-11-26T16:55:46.616702Z |
| 123 | `approval_requested` | 2026-11-26T16:55:46.616702Z |
| 124 | `stage_blocked` | 2026-11-26T16:55:46.616702Z |
| 125 | `approval_granted` | 2026-11-26T16:55:46.741657Z |
| 126 | `approval_consumed` | 2026-11-26T16:55:46.747741Z |
| 127 | `operation_intent` | 2026-11-26T16:55:46.747741Z |
| 128 | `model_exchanged` | 2026-11-26T16:55:46.755847Z |
| 129 | `operation_confirmed` | 2026-11-26T16:55:46.747741Z |
| 130 | `stage_completed` | 2026-11-26T16:55:46.747741Z |
| 131 | `run_finished` | 2026-11-26T16:55:46.747741Z |

The chain ends at `run_finished` — not at `model_exchanged` as the first
round's did. The run row reads `finished` (finished_at
`2026-11-26T16:55:46.747741Z`); the stage row reads `completed`
(`blocked_reason` null).

**Gap 2 is closed on the pilot copy:** the stage that was parked on the
approval is completed and the run is finished, in one unit, after the
request is answered.

---

## 4. What the replay did not exercise

**The advisor loop cannot run on this copy.** The first round's
`roles run` refusal (`role_comment_not_in_the_chain`) is the product's own
and it is right: the chain holds no comment under the first round's key
`pilot-paper-002:p[7]`. The replay's successful consent-gate run used a
different project's chain (`proj-pilot-2`, issue key
`iss-c2-<redacted>-15`), which does hold a comment; the advisor's marks were
not exercised, because the injected answer is fixed and no role work
beyond the trajectory candidate was driven.

**The CLI still has no model request of its own.** The product's only CLI
route to a model is `roles run`, and on this copy it refuses before the
wire (the chain holds no comment under the first round's key). The
consent-gate replay therefore drove the spend through the application
layer with an injected `send`; the CLI's own spend path was not exercised.

**No real model request was made.** The injected `send` returns a fixed
`ModelInvocation` (`provider` `minimax`, `model` `MiniMax-M3.1-Flash`,
`credential_fingerprint` `fake`, one exchange record with a zero digest);
no credential was read, no key was printed or written, and no money was
spent. The exchange event's `credential_fingerprint` in the log is the
injected `fake`, not the pilot's real
`d8053fe1…c9a7b`.

---

## 5. Where each number came from

| number | value | command that produced it | measured against |
|---|---|---|---|
| tree | `9d3d4a77d67b7865ccacdfc0066f6fe205cd2fba` | `git rev-parse HEAD` | this worktree |
| before revision | `0032` | `SELECT version_num FROM alembic_version` (read-only) | pilot store, before |
| after revision | `0034` | `upgrade_to_head` then `current_revision` | pilot store, after |
| before events | `10,305` | `SELECT count(*) FROM events` (read-only) | pilot store, before |
| after events | `10,401` | `SELECT count(*) FROM events` (read-only) | pilot store, after |
| replay events (16:48+) | `96` | `SELECT count(*) FROM events WHERE occurred_at >= '2026-11-26T16:48:00'` | pilot store, after |
| refusal_recorded in replay | `9` | `SELECT count(*) FROM events WHERE type='refusal_recorded' AND occurred_at >= '2026-11-26T16:48:00'` | pilot store, after |
| refusal exit code | `3` | `roles run … ; echo $?` | CLI, this tree |
| refusal seq | `74` | `SELECT seq, type … ORDER BY rowid` | pilot store, after |
| approval_id (ask) | `01a218c4-5f0c-767d-b288-4198690c3280` | `roles run` (no `--approval`) | CLI, this tree |
| args_digest | `024ca59b4267f8791cc34a0affe291e7cd54de52ac4ab8c94eb8e41ec1f18739` | `task approval-grant` output | CLI, this tree |
| closure chain | seq 120–131 | `SELECT seq, type … WHERE occurred_at LIKE '2026-11-26T16:55%'` | pilot store, after |
| run status | `finished` | `SELECT run_id, status … ORDER BY rowid DESC LIMIT 1` | pilot store, after |
| stage status | `completed` | `SELECT stage_id, status … ORDER BY rowid DESC LIMIT 1` | pilot store, after |
| db sha256 (after) | `b16a8fcf525a17ecfc36cd5382bd43d8f256849ba39bd09c0ca2301724899fac` | `sha256sum labcairn.db` | pilot store, after |
| material sha256 | `04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d` | first round's record; unchanged | source `src-0ac499ea4d3a7d82` |
| policy digest | `2f0d7827d44c4fa81577e871f856ceadf33f12443c718e8727d4292c993d4da6` | `task approval-grant` output; unchanged | policy |

**The store's revision and event count moved, and that is the point of the
window.** The before-measurement was taken read-only; the migration and the
replay are writes. The pilot's task and source ids are unchanged.

---

## 6. Where the material and the evidence live

The material stays in the workspace, outside the repository, under
`E:/labcairn-local/` — `docs/ci/external-paths.json` answers for every
path a tracked file names. The pilot workspace is
`E:/labcairn-local/pilot-ws`; its store is `labcairn.db` (sha256 after
this replay `b16a8fcf…99fac`); the material is
`materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`
(8,805,237 bytes, sha256 `04cc31be…a6172d`). The replay's temporary driver
lives in the session's shared notes directory, outside the repository, and
is not part of the tree. No credential, key or material text was written
into this record or into any file in the repository.

---

## 7. What this record does not stand in for

This is a replay of the bookkeeping, not a pilot record. It does not
replace [`LC-P4-PILOT-first-round-2026-11-26.md`](LC-P4-PILOT-first-round-2026-11-26.md),
which ran a whole round with a real model request; it measures that the two
gaps that round found are closed on the same copy, with the refusal now in
the log and the stage and run now closing. The advisor loop and the CLI's
own model request remain unexercised, for the reasons §4 gives.