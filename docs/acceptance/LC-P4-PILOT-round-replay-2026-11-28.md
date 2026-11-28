# LC-P4-PILOT — the round, replayed on the tree as it stands

**Ticket:** LC-P4-PILOT (the pilot's real-world acceptance, replayed against
the tree that has gained the evidence gate, the report's refusal over a moved
source, the command line's drawing of the gate's verdict, the verify door,
the abstention path, and the Chinese removed from the tree).
**Date:** 2026-11-28.
**Tree:** `19a7fc730a6886c189c11d8e0a92adde630578e6`, the commit this work
sits on; the change is the commit that carries this record. Worktree
`.claude/worktrees/youthful-mclaren-83fe78`, branch
`claude/youthful-mclaren-83fe78`. Windows 11 Pro (10.0.26300 x64, AMD64),
Python 3.12.10 (a worktree-local `.venv`, created by `uv sync --frozen`).
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. **This window changed nothing under `src/` and nothing under
`tests/`** — it measured and recorded.

**The tree the round ran against.** The `.venv` in this worktree was created
by `uv sync --frozen` and its editable install names this worktree's own
`src/` (`E:\LabCairn\.claude\worktrees\youthful-mclaren-83fe78\src`); every
command below was run through this worktree's own console script
(`.venv/Scripts/labcairn.exe`), not the main checkout's.

**Workspace:** the pilot copy the first round ran on,
`E:/labcairn-local/pilot-ws`, **copied** into a round's own workspace under
`E:/labcairn-local/tmp` before anything ran, so the pilot's own workspace
keeps the state it had. (The copy's own path is not named here: the
external-path ledger requires an entry of its own for every external path a
record names, and this window does not own that ledger.) **Before the round**
the store was at revision `0032` in the first round's reading and `0034`
after the replay's migration, held `10,401` events, and its current task was
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1` ("Pilot revision round 2
(desensitised copy pilot-paper-002)"). **After the round** the copy is at
revision `0035` and holds `10,411` events.
**Material:** the same source row, `src-0ac499ea4d3a7d82`,
`pilot-paper-002.docx`, sha256
`04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`,
8,805,237 bytes, `readable`, resource key
`pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`.

**What is claimed here.** The round's own steps ran on this tree against the
pilot's own material, and each surface the last batch added did what it says
it does — with one exception, which §5 names and §6 measures. The commands,
the ids, the digests, the counts, the statuses and the exit codes below were
measured on this tree; where a step stopped, the record says where and why.

**What is not claimed.** That a real model request was made — **none was**;
the round's own rule is that a real request costs the owner money and leaves
the machine, so the project's own fakes serve. That the consent gate was
driven — it was not, because the copy reaches its abstention before the
wire. That the material under `E:/trial-material/` was read — **it was not**;
the product reads it, the window does not.

**The boundary this record obeys.** Ids, digests, counts, lengths, statuses
and paths. No sentence of the manuscript, no extracted text, no picture, and
no key. The claims the round recorded are **statements about** the passages
they are anchored to, written by this round in English; none of them quotes
the material, and the report describes them by their digests and lengths
only. **A name that carries a person is material too**: the workspace's own
issue keys for the second corpus are not reproduced here, and the one the
round used (`pilot-paper-002:p[7]`) carries no person.

---

## 1. The migration, and the state before

`labcairn doctor --json` on the round's copy: the workspace is initialised,
the database is at revision `0034` and `at_head: false` — **the tree's head
is `0035`** — and the policy is the one the pilot has been running under,
digest `2f0d7827d44c4fa81577e871f856ceadf33f12443c718e8727d4292c993d4da6`.
The provider is `minimax` over the `anthropic` protocol, model
`MiniMax-M3.1-Flash`, and the doctor's four capability readings are
`unverified` with the reason "no probe record for this endpoint, model and
protocol", as the first round recorded.

The migration was applied explicitly, the way the product applies it when it
opens a store:

```python
from labcairn.db.migrations import current_revision, upgrade_to_head
upgrade_to_head(<the round's copy>/labcairn.db)
```

`current_revision` read `0034` before and `0035` after. The migration is
`0035_role_abstention_event`, and **the events table's row count was
unchanged by the migration itself** (10,401 before and after) — a migration
that adds an event type adds a vocabulary, not a row.

## 2. The round's own steps

| # | Command | What it produced | Exit |
|---|---|---|---|
| 1 | `sources inspect --source src-0ac499ea4d3a7d82 --json` | the source as the ledger holds it: `docx`, `readable`, 8,805,237 bytes, the digest above, `identifiers: []`, the resource key. No text. | 0 |
| 2 | `sources addresses --source src-0ac499ea4d3a7d82 --json` | **268 addresses**, all `docx`, one extraction version `8ef92c6207f7dcab216ce4eaf8524096`; **251 `accepted` / 17 `rejected`**; 251 with text; longest 651 characters, median 24 | 0 |
| 3 | `task claim --source src-0ac499ea4d3a7d82 --address <p[4]> --kind claim --text <statement> --json` | evidence `01a2215c-71fb-7e8b-b57a-08aa4530d932`, anchor `01a2215c-71fa-7018-8761-4780bbd2aa91`, status `extracted`, bound to the source's content hash | 0 |
| 4 | `task claim-verify 01a2215c-71fb-7e8b-b57a-08aa4530d932 --check c1 --json` | status `extracted` → **`verified_by_rule`**; the log gains one entry: `c1`, checker `c1.source_exists`, outcome `pass` | 0 |
| 5 | `task report --path report --json` | receipt `…-r3-document`, `report.json` sha256 `7f1708f3…d474bd7`, 2,517 bytes, revision 3, `staleness: current` | 0 |
| 6 | `task report --path report` | the same revision at the terminal, with the gate's verdict drawn — §4 | 0 |
| 7 | `artifacts list --json` | **24 artifacts**, all `current` — the first round's 12 plus this round's 12 | 0 |

**The addresses match the first round exactly**: 268 addresses, 251 accepted,
17 rejected, one extraction version, longest 651 characters. The rejected
locators are the document's own `del` elements; the accepted ones are its
paragraphs. The `p[7]` locator is
`k=4:docx|p=17:word/document.xml|e=25:/w:document/w:body/w:p[7]|v=8:accepted|c=5:0-432`,
432 characters — **the same address the first round claimed at**, which is
why the round claimed at `p[4]`, `p[8]`, `p[9]` and `p[10]` instead: one
record per span per task, and the round needed claims of its own.

**The report's own body.** Two claims and two footnotes, one section
("Findings"), and a `snapshot` naming both records:
`01a217a3-5845-78c6-a41f-e0093a0b7d2e` and `01a2215c-71fb-7e8b-b57a-08aa4530d932`.
The second is the `verified_by_rule` one, so **the rule's pass reached the
report's own text** — the record is named as established in the document the
gate judged.

## 3. The verify door, on real material

**What a rule's pass takes to reach.** The door is
`labcairn task claim-verify <evidence-id> --check c1|c2|c3`. It runs the rule
against the ledger's own anchors and appends the verdict to the record's log
before it judges the move; the status moves only if the verdict is a pass.

Measured on the pilot's material:

| the claim | the check | the log gained | the status | Exit |
|---|---|---|---|---|
| `01a2215c-71fb-7e8b-b57a-08aa4530d932` (p[4]) | `c1` | `c1` / `c1.source_exists` / `pass` — "all 1 anchor(s) resolved and every recorded content hash still matches the source" | `extracted` → **`verified_by_rule`** | 0 |
| `01a22161-5a7b-75a8-9d90-a1c963524643` (p[8]) | `c2` | `c2` / `c2.quotation_match` / `pass` — "the quoted span appears character-for-character in the located text" | `extracted` → **`verified_by_rule`** | 0 |
| `01a22167-7481-…` (p[9]) | `c1` | as above | `extracted` → **`verified_by_rule`** | 0 |

At the terminal the door says what it did, in one line:

```
verified 01a22167-7481-70ac-add6-0a022d0ca3ec — c1 returned pass: all 1
anchor(s) resolved and every recorded content hash still matches the source
```

**C2's pass is a property of the round's own claim, not of the material.**
C2 checks that the record's *span* appears character-for-character in the
located text, and the span is copied out of the locator when the claim is
recorded — so C2 confirms the round's own bookkeeping rather than the
manuscript. It is the C1 verdict that says something about the material.

**The door's refusals, all on the pilot's real records.** Four ways in, four
refusals, and **not one of them wrote a log entry** — the records' logs were
read afterwards and still hold exactly the entries above:

| the request | the reason | Exit |
|---|---|---|
| `--check c4` | `arguments_invalid` — "'c4' cannot verify a claim. The checks whose pass moves a record to 'verified_by_rule' are c1, c2, c3. A C4 entry is a person's attestation's own record of not checking, and it never passes." | 3 |
| `--check c9` | `invalid_arguments` — "'c9' is not a check this build runs. The checks are c1, c2, c3, c4; the ones that can verify a claim are c1, c2 and c3." | 3 |
| a claim id that is not a UUIDv7 | `invalid_arguments` — "'not-an-id' is not a claim id: claim ids are UUIDv7." | 3 |
| a record that is already `verified_by_rule` | `verification_refused` — the **transition**, not the rule: "ADR-0004 Contract 2 does not allow 'verified_by_rule' -> 'verified_by_rule'." | 3 |
| a record that is `user_attested` | `verification_refused` — the transition: "does not allow 'user_attested' -> 'verified_by_rule'." | 3 |

The last two are the **state machine**, not the door: `user_attested → verified_by_rule`
and `verified_by_rule → verified_by_rule` are not legal transitions, so the
rule never ran ("the rule 'c1' did not run, because the move was refused
first"). The door is right to refuse, and the refusal says so honestly.

## 4. The command line's drawing of the gate's verdict

`task report --path report` at the terminal, on the pilot's real material:

```
output/01a212be-ddd1-7c9a-aaad-c1db083b8bc1/report/v4/report.json — revision 4,
02ee68648d5cf468f4a3c042af5dfb5bb51ce08b8b0f88cf3a69bf9ec479646a.
3 link(s) in its chain; the four forms are beside it under the task's output
area, and `labcairn artifacts list` names them.
┌──────────────────────────── evidence gate ─────────────────────────────┐
│ evidence gate  passed, over 2 record(s)                              │
│ judged         01a217a3-5845-78c6-a41f-e0093a0b7d2e, 01a2215c-71fb-7e8b-b57a-08aa4530d932 │
│ unjudged       (none)                                                │
│ findings       0                                                     │
└────────────────────────────────────────────────────────────────────────┘
```

The same verdict in `--json`: `evidence_gate` carries `passed: true`,
`considered` (the two record ids), `findings: []`, and `unjudged_records: []`
beside it. **Both halves are on the human rendering** — the records the gate
judged and the records the report names without judging — and a reader at the
terminal sees the gate's extent rather than only that a report was written.

## 5. A report over a source that has moved

The round moved the material in **its own copy** by one byte — the last byte
of the file, so the size is unchanged (8,805,237 bytes) and the digest alone
moves:

| | digest |
|---|---|
| the ledger holds | `04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d` |
| the file now hashes to | `9129cfc90fdc895523aec96ee4d5d18103acd01c8abf6cc8f6dc702635863467` |

**The report refused, and wrote nothing.** Exit **3**, reason
`report_evidence_refused`:

```
1 source(s) the report cites are not the bytes the ledger describes:
'src-0ac499ea4d3a7d82' (materials/pilot/LC-P4-PILOT/desensitised-copy/
pilot-paper-002.docx) has moved: the ledger holds 04cc31be…a6172d, and the
file now hashes to 9129cfc9…63467. ADR-0004 I4 invalidates a record whose
source has moved rather than refreshing it, so the report is refused before
it is written … Nothing was written.
```

**Nothing was written, and this was checked rather than assumed**: the
task's report directory holds `v1`, `v2`, `v3`, `v4` — **no `v5`**. The
human form prints the same refusal on stderr with the same exit code.

**The gate alone does not see it.** Asked directly over the same moved
material, the gate **passed** all three doors — the subset door over the
round's own claim, the subset door over the first round's attested claim, and
the whole-task door — with `findings: []`. That is the drift record's own
reason: the gate's index answers from the ledger, whose `content_sha256` is
never refreshed, so it cannot see a file edited on disk since ingestion.
**Only the render opens the file.** Two doors, two questions, and neither
one can pass a source the other refuses.

**The second door, reached through the remedy.** `sources ingest` **does**
move the ledger's row — the source row's `content_sha256` became
`9129cfc9…63467` and its `ingested_at` became `2026-11-28T09:07:49Z` — so
the file and the ledger agree again, and the report is then refused by the
**gate** instead, with one `drift` finding per record:

> `01a217a3-5845-78c6-a41f-e0093a0b7d2e (drift)`: the record is stated as
> established and its log records no C1 verdict, so the gate asked the source
> itself: C1 concludes 'fail' — 1 of 1 cited anchor(s) do not hold: the
> source behind anchor '…' changed after the anchor was made (bound to
> `04cc31be…`, now `9129cfc9…`). The address still resolves, but not at the
> bytes the record was made against.

That is the drift record's design, working on real material: **the render's
door compares the file with the ledger, and the gate's door compares the
record with the ledger**, and the two refuse on their own links.

**`task run --source` does not move the ledger's row.** The round ran it as
the re-ingest, and the stage's `output_hashes` still held
`04cc31be…a6172d` — the old digest — and the source row's `content_sha256`
did not move. **Only `sources ingest` does.** A reader who reaches for
`task run` first, because that is what the first round's step 1 did, will
not get past the door.

## 6. What broke: the refusal names a remedy no surface can carry out

**This is the round's most valuable finding, and it is a real gap.**

The refusal's own message ends with its remedy:

> "Nothing was written. **Ingest the material again, then re-verify or
> re-attest the claims it carries.**"

The round followed that sentence exactly, on the pilot's real records, and
every step after the ingest refused:

| the remedy's step | what it did | Exit |
|---|---|---|
| "Ingest the material again" | `sources ingest --json` — **works**; the source row's digest moves | 0 |
| "…then re-verify … the claims it carries" | `task claim-verify <claim> --check c1` on **all four** citable records | **3**, `verification_refused` |
| "…or re-attest the claims it carries" | `task claim-attest <claim> --user local-user --note …` on the same records | **3**, `attestation_refused` |

The two refusals, in the product's own words — and **both name `extracted` as
the state they would have to go through**:

> `verification_refused`: the rule 'c1' did not run, because the move was
> refused first. The record '…' did not move to 'verified_by_rule': ADR-0004
> Contract 2 does not allow 'user_attested' -> 'verified_by_rule'. Allowed
> from 'user_attested': ['conflicted', 'extracted', 'unsupported'].

> `attestation_refused`: the ledger refused the attestation: ADR-0004
> Contract 2 does not allow 'user_attested' -> 'user_attested'. Allowed from
> 'user_attested': ['conflicted', 'extracted', 'unsupported'].

The four citable records are one `user_attested` (the first round's) and
three `verified_by_rule` (the round's own), and the second refusal has the
same shape on the other kind: *"does not allow 'verified_by_rule' ->
'user_attested'"*. **So the refusal is the same for every record and every
door: the only state from which either a rule's pass or a person's word can
be written is `extracted`, and there is no way there.**

**Both legal transitions point at `extracted`, and no surface can perform
them.** Read from the tree:

- `ALLOWED_TRANSITIONS` in `src/labcairn/evidence/store.py` allows
  `user_attested → extracted` and `verified_by_rule → extracted`. The
  transitions are legal.
- **Nothing in `src/` writes `extracted` as a transition.** Every mention of
  `VerificationStatus.EXTRACTED` under `src/` is one of two things: a
  *new* record's status at creation (`application/evidence.py:331` and
  `:818`), or the table's own rows. The store's status `UPDATE` is written
  by `advance` and by `attest` — and their only callers are
  `application/evidence.py:590` (`advance` → `verified_by_rule`) and
  `application/evidence.py:481` and `:835` (`attest` → `user_attested`).
  `supersede_record` is reachable only from the proposal settlement path,
  and it writes a *new* row.
- So **every citable record is a one-way door once it is citable**: the two
  writers can only write the two citable statuses, and the transition back
  to the state a rule or an attestation can be written from has no writer.

**The consequence, measured.** A fresh claim at a *different* address can be
made and verified cleanly — `01a2216e-1a02-7adc-ba1d-606cdfcf8c54` at
`p[10]`, `extracted` → `verified_by_rule` with a C1 pass — **and the report
still refuses**, because the gate judges the four drifted records as well and
it refuses the **set** rather than the record:

> the evidence gate refused the report before anything was written: 4
> objection(s) over the 5 record(s) the report states as established.

**So a task whose material moved cannot produce a report again.** The
material's own bytes moved, the records that rest on them are drifted, and
the two doors that could clear them — the verify door and the attestation
door — are closed by the state machine, and the state machine has no surface
that opens them.

**What would close it.** A surface that moves a citable record back to
`extracted` — the transition the table already allows, and the one both
refusals name in their "Allowed from" list. The verify door is the natural
home for it: the record's own status is the thing it is asked about, and the
store is already the only writer of that column. This is a **finding, not a
change** — this window changed nothing under `src/`, and the gap is left for
the owner to decide on.

## 7. The advisor loop, and the abstention path the tree gained

`roles run` against the pilot's copy, and the tree has moved since the first
round recorded it:

| the request | the answer | Exit |
|---|---|---|
| `--role trajectory --project proj-pilot-002 --issue-key pilot-paper-002:p[7]` | **refused**: `role_run_material_mismatch` — "the request declares the material as {'root id': '', 'resource key': '', 'material ref': ''}, and the chain holds it as {'root id': 'source:0', 'resource key': 'pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx', 'material ref': 'materials/…'}; material ref, resource key, root id differ" | 3 |
| the same, **with** `--root source:0 --resource-key <key> --material-ref <ref>` | **abstained**: exit 0, `answer` `null`, `exchange_event_id` `null`, `verdict` `null`, and an `abstention` of `role_id` `trajectory`, `role_version` 1, `what_is_missing` "the chain holds no comment for this document", `note` "the advisor wrote nothing in the margins of this document, so there is no mark to align a change against"; the `shape` reads 0 comments, 0 revisions, 1 version | 0 |

**The first round's `role_comment_not_in_the_chain` is not gone — it is
reached later.** Both refusals are live in the tree
(`application/roles_run.py:1044` and `:1128`), and the tree now asks the
**material declaration** first, so a request that declares no material is
refused for the declaration before the chain is consulted. **With the
material declared correctly, the run reaches the chain and finds the other
reason** — and then abstains, because a chain with no comment is not a
failure but an absence. The **abstention** is the tree's newer surface —
migration `0035` exists for it — and it is the right answer here: the copy
holds no comment under this key, so the role has nothing to align a change
against, and the product says so instead of refusing the whole operation.

**Both are in the log.** The refusal is `seq 172`, `refusal_recorded`, with
`reason` `role_run_material_mismatch` and `asked_for` naming the project,
the issue key, the operation and the role — ids and keys, never the
material's text. The abstentions are `seq 173` and `seq 174`,
`role_abstention_recorded`, with `missing`, `project_id` and `roles`. **The
refusal reached the log**, which is what the replay of 2026-11-27 closed.

## 8. The demonstrations

**`examples/g4_exit_demo.py` — exit 0.** It shows the refusal with a control
and a witness each. The material it ingests is changed, and the repository's
own measurement says so:

```
the ledger recorded : 1c74e71d72ce676838e78fc4aeb7cd7303e210268430b5fe143e83173226373f
the file now hashes : b2da5b9315d506f16052e97451a06b3fb0cc686f97a76d4f8d567baf8b5c1f9f
[ok] the repository's own measurement says the material moved
stale artefacts : 8
[ok] the repository's own walk marked the artefacts whose chain names the material  - 8 of 8 stale receipt(s) name the material
[ok] with the repository's own reason, and not one invented here  - stale: a source material changed after this artifact was produced. …
```

and the staleness comparison carries **its own control** ("the staleness
requirement finds the difference it was given — a receipt given another
reason does not qualify, so not every receipt does"). This is the
demonstration the CLI-gate-rendering record said had not caught up with the
drift door: it has now.

**And it shows the refusal itself, over its own material:**

```
refusal    : report_evidence_refused
because    : 1 source(s) the report cites are not the bytes the ledger
describes: 'src-37745d0474b81c2f' (materials/groups.csv) has moved: the
ledger holds 1c74e71d…, and the file now hashes to b2da5b93…. ADR-0004 I4
invalidates a record whose source has moved rather than refreshing it, so
the report is refused before it is written … Nothing was written.
[ok] the re-render is refused, because the material it cites has moved  - report_evidence_refused
[ok] and the refusal names the source, the ledger's bytes and the file's bytes  - src-37745d0474b81c2f
[ok] the comparison the refusal rests on found a difference, and only the file moved  - the ledger holds 1c74e71d72ce, the file has b2da5b9315d5
```

**Two things worth naming.** The demonstration reaches the refusal **through
the product's own surfaces** — the re-render is refused, and the refusal's
own sentence is quoted, not restated. And the demonstration says, in its own
"what this run did not show" list, that **it did not take the refusal's
remedy**: *"The refusal names its own remedy -- ingest the material again,
then re-verify or re-attest the claims it carries -- and this run did not
take it."* **§6 is that gap, measured on the pilot's own material** — the
demonstration knew the remedy was untaken, and the round took it and found
that it cannot be carried out.

**`scripts/outsider_path.py` — exit 0, in `witness` mode.** The script
clones the repository into a directory of its own, builds an environment
**inside the clone**, and runs the README's commands there — so the code
under test is the clone's code, not this worktree's. Measured:

| | |
|---|---|
| the clone's head | `19a7fc730a6886c189c11d8e0a92adde630578e6` — **this tree's commit**, and the script prints the commit it loaded the code from |
| the package the walk ran | `…/clone/src/labcairn/__init__.py` — the clone's own |
| checks | **108 passed**, `failure: null`, exit 0 |
| the README's commands | **11 run, 11 documented** — the extraction is compared in both directions, so a command the README shows that the walk does not run is a failure, and the reverse too |
| the wall clock | 145.6 s |
| the report's recomputation | "rendered as v2" |

The walk also ran the README's own `uv run ruff check .`,
`uv run ruff format --check .` and `uv run mypy` **in the clone** — all
exit 0 — and left the lockfiles alone ("rewrote: []"). The suite command
was reduced to a collection, because running the whole suite from inside
the suite would recurse; the web package's commands were not run, and the
script says so by name.

**What the outsider path does not show about the drift**, and why that is
the right shape for it to be: it runs on **its own synthetic material** (a
CSV of the tests' own), not the pilot's, so it cannot say anything about
the pilot's records. What it does show is that **the README's commands work
from a clean clone at this commit** — which is the claim it makes.

## 9. What the round could not measure, and why

- **No real model request was made.** The round's own rule, and the owner's
  money. The consent gate was therefore not driven: the copy reaches its
  abstention before the wire, and the round did not spend an approval. **The
  round therefore did not measure the consent gate's own behaviour** — the
  approval's ask, its grant, its consumption and the run's closure — which
  the 2026-11-27 replay measured and this tree has not changed.
- **The material under `E:/trial-material/` was not read.** The product
  reads it; the window does not. The round ran entirely on the pilot
  workspace's own copy.
- **The pilot's own workspace was not modified.** The round ran on a copy.
  The pilot's store is still at revision `0034` with `10,401` events, as the
  replay left it.
- **The drift was made by a one-byte change, not by a real edit.** That is
  enough to move the digest and is what the drift door is about, but it is
  not a re-save of the manuscript by an editor.
- **The whole-suite test run was not done here.** The outsider path's
  `witness` mode reduces the README's suite command to a collection, and
  this window adds one document and no test file, so the shard costs do not
  move; the run is the integrating session's.
- **The round's own scratch lives outside the repository**, under
  `E:/labcairn-local`, and is not named here: the external-path ledger
  (`docs/ci/external-paths.json`) requires every external path a record names
  to have **an entry of its own**, and this window does not own that ledger.
  The paths this record does name — `E:/labcairn-local/pilot-ws` and
  `E:/labcairn-local/tmp` — are both ledgered.

## 10. Where each number came from

| number | value | command that produced it | measured against |
|---|---|---|---|
| tree | `19a7fc730a6886c189c11d8e0a92adde630578e6` | `git rev-parse HEAD` | this worktree |
| revision before | `0034` | `SELECT version_num FROM alembic_version` (read-only) | the round's copy, before |
| revision after | `0035` | `upgrade_to_head` then `current_revision` | the round's copy, after |
| events before / after the migration | 10,401 / 10,401 | `SELECT count(*) FROM events` | the round's copy |
| events after the round | 10,411 | `SELECT count(*) FROM events` | the round's copy |
| addresses | 268 | `sources addresses --json` | the round's copy |
| accepted / rejected | 251 / 17 | the `v=` field of the locator keys the product printed | the round's copy |
| with text / longest / median | 251 / 651 / 24 | the same payload, measured | the round's copy |
| the round's claims | 5 | `task claim --json` | the round's copy |
| citable records at the end | 5 | `evidence_records` | the round's copy |
| artifacts | 24, all `current` | `artifacts list --json` | the round's copy |
| the report's receipt | `…-r3-document`, `7f1708f356373f72d8e493a697f5d365c0be7fd5b5987678e9ccac840d474bd7`, 2,517 bytes | `task report --json` | the round's copy |
| the ledger's digest | `04cc31be…a6172d` | `sources inspect --json` | the round's copy |
| the moved file's digest | `9129cfc9…63467` | sha256 of the file after the one-byte change | the round's copy |
| the outsider path | 108 checks passed, `failure: null`, 145.6 s, 11 README commands run and 11 documented | `scripts/outsider_path.py --mode witness` | the clone, at this commit |
| the clone's head | `19a7fc730a6886c189c11d8e0a92adde630578e6` | the script's own report | the clone |

## 11. The commands, and their real results

Every command was run from this worktree, against the round's copy, through
this worktree's own console script:

```sh
export TEMP="E:/labcairn-local/tmp" TMP="E:/labcairn-local/tmp" \
       MPLCONFIGDIR="E:/labcairn-local/tmp/mpl" COLUMNS=200
<worktree>/.venv/Scripts/labcairn.exe --workspace <the round's copy> \
    <command> [--json]
```

The exit codes are the commands' own, read from the command and not from a
pipe. The full list, with each command's output file, is in §2 and §3–§8;
the two statuses worth restating are the refusals' **3** and the successes'
**0**.

**A note on the copy.** The round's copy was made with `robocopy /E /COPY:DAT
/DCOPY:DAT` — 262 files, 2.167 GB, robocopy's exit 1 (files copied
successfully). The pilot's own workspace was not touched.
