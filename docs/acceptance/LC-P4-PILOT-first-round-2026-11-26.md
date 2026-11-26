# LC-P4-PILOT — one whole round on the pilot copy

**Ticket:** LC-P4-PILOT (the pilot's first round, on the imported copy)
**Date:** 2026-11-26.
**Tree:** `64f1bb7e4a15e8ca72180864ea1067cadc6ce340` (worktree
`charming-wiles-ae095c`), Windows 11 Pro (10.0.26300 x64, AMD64),
Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Workspace:** `E:/labcairn-local/pilot-ws` — database revision `0032`, at
head; task `01a212be-ddd1-7c9a-aaad-c1db083b8bc1` ("Pilot revision round 2
(desensitised copy pilot-paper-002)"); paper project `proj-pilot-002`;
input version `ver-pilot-002-input`.
**Material:** source `src-0ac499ea4d3a7d82`, `pilot-paper-002.docx`, sha256
`04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`,
8,805,237 bytes, `docx`, `readable`, resource key
`pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`.
**Policy:** digest `2f0d7827d44c4fa81577e871f856ceadf33f12443c718e8727d4292c993d4da6`.
**Authorisation:** the owner's signed record,
[`LC-P4-PILOT-model-authorisation-draft.md`](../plans/LC-P4-PILOT-model-authorisation-draft.md)
(§1 provider and model, §2 scope, §3 request content, §4 budget, §5 timeout);
the grant the run spent is
`grant-model-suggestions-pilot/LC-P4-PILOT` — scope
`pilot/LC-P4-PILOT/desensitised-copy/**`, subject
`pilot/LC-P4-PILOT/desensitised-copy`, destination
`https://api.minimax.cn/anthropic`, granted by `owner` on 2026-11-24, expiring
2026-12-24.

**What is claimed here.** The pilot's copy went through **one whole round**
— analysis → evidence → report → export — on the product's own surfaces,
with one real model request behind the consent gate in the middle of it.
The commands, the ids, the digests, the counts, the statuses and the timings
below were measured on this tree; where a step stopped, the record says where
and why.

**What is not claimed.** That the pilot's **suggestion loop** ran — it did
not, and §4 says why. That the round exercised the advisor's marks — it
could not, and §4 says why. That the model answer was checked — it was not,
and the report says so in its own words ("interpretation not machine-verified").
That the product's **CLI** carried the model request — it could not, and §3
says which surface did.

**The boundary this record obeys.** Ids, digests, counts, timings and paths.
No sentence of the manuscript, no extracted text, no picture, and no key. The
claim this round recorded is a statement about the passage it is anchored to,
not a quotation of it, and the model answer is described by its shape and its
digest only. The material stays in the workspace.

---

## 1. What was read, before anything ran

`labcairn doctor --json` on the pilot workspace: the workspace is
initialised, the database is at revision `0032`, and the policy is the one
the pilot has been running under — `source.inventory`, `source.read`,
`analysis.run` and `report.render` allowed, dotfiles denied, and **every
network effect asked for**. The provider is `minimax` over the `anthropic`
protocol, model `MiniMax-M3.1-Flash`, endpoint fingerprint
`db47efa5986d25d9bae6a7d9788a5b0b7d5db0240a83c29aefb42ac0420f385c`,
timeout 60 s, with the credential's fingerprint
`d8053fe1b4c635e4903517299a3db2904be2943408a097d65262466d02dc9a7b`. The
doctor reports all four of the provider's capabilities (`tool_calls`,
`structured_output_native`, `structured_output_prompted`, `usage_reporting`)
as `unverified` and `usable: false`, with the reason "no probe record for
this endpoint, model and protocol" and `probe_source: none` — the probe was
run on 2026-11-25 and its record lives outside this workspace
([`LC-P4-PILOT-capability-probe-2026-11-25.md`](LC-P4-PILOT-capability-probe-2026-11-25.md)).
**That flag did not stop the round:** the request below went out and came
back.

## 2. The round, step by step

Every command was run from the worktree above, against the workspace above,
with the product's own console script.

| # | Command | What it produced | Time |
|---|---|---|---|
| 1 | `task run --source src-0ac499ea4d3a7d82 --json` | stage `01a217a2-d1f4-7a88-bf50-aae7bf213340`, name `inventory`, status `completed`; output hash `04cc31be…24a6172d`; operation `01a217a2-d1ff-72fc-a08e-3cd80ee2a2a7`, capability `source.inventory`, state `confirmed`, resource key `pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` | 1.97 s |
| 2 | `sources inspect --source src-0ac499ea4d3a7d82 --json` | the source as the ledger holds it: `docx`, `readable`, 8,805,237 bytes, the digest above, `identifiers: []`, and the resource key. No text. | 2.23 s |
| 3 | `sources addresses --source src-0ac499ea4d3a7d82 --json` | **268 addresses**, all `docx`, one extraction version `8ef92c6207f7dcab216ce4eaf8524096`; **251 `accepted` / 17 `rejected`**; 250 with non-empty text; longest text 651 characters, median 24 | 2.21 s |
| 4 | `task claim --source src-0ac499ea4d3a7d82 --address <p[7] locator> --kind claim --text <statement> --json` | evidence `01a217a3-5845-78c6-a41f-e0093a0b7d2e`, anchor `01a217a3-5844-772e-a92a-a1da3faf30bf`, status `extracted`, `extracted_span_sha256` `67a95b2d…052118e`, bound to the source's content hash, created by `local-user` | 2.04 s |
| 5 | `task approval-request --capability model.request --root source:0 --resource-key pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx --arguments-json {…}` | operation `01a217a4-839b-7592-b290-f91175c89b74`, state `awaiting_approval`, `args_digest` `3ba0bd4c…d486d636`; approval `01a217a4-839b-7593-91a9-b466a88c4a06`, state `pending`, expiring `2026-11-26T12:06:27Z` | 1.96 s |
| 6 | `task approval-grant 01a217a4-839b-7593-91a9-b466a88c4a06 --json` | state `granted`, `granted_at` `2026-11-26T11:36:31Z`, `grant_policy_digest` `2f0d7827…993d4da6` — the policy digest, so the grant is bound to the policy the doctor printed | 1.96 s |
| 7 | the real request — §3 | approval `granted` → `consumed`; exchange event `01a217a5-5f04-7a21-8007-31f395f0d8fc` | 10.51 s on the wire |
| 8 | `task claim-attest 01a217a3-5845-78c6-a41f-e0093a0b7d2e --user local-user --note <…> --json` | status `extracted` → `user_attested`; the verification log carries one C4 entry, `outcome: not_checked`, `checker_id: local-user` | 1.92 s |
| 9 | `task report --path report --json` | receipt `…-r1-document`, `report.json` sha256 `29c7dcef…0757d6c`, 1,461 bytes, revision 1, `staleness: current` | 3.43 s |
| 10 | `task report --path report --json` (again, after the attestation) | receipt `…-r2-document`, `report.json` sha256 `3904ea81…4cf266c`, 1,465 bytes, revision 2, `staleness: current` | 2.56 s |
| 11 | `artifacts list --json` | **12 artifacts** — six per revision (§5) | — |

**The claim's anchor.** The address step 4 used is the introduction's
framing paragraph, `…/w:document/w:body/w:p[7]`, `accepted` view, characters
0–432. The claim is a statement about that paragraph, not a copy of it, and
the ledger's own bytes back it: the text the claim's span was taken from
hashes to `67a95b2d…052118e`, which is the same digest the anchor recorded
and the same digest the evidence record carries. **Three digests, one
value** — the claim is anchored to the imported copy's bytes, not to a
paraphrase of them.

**The report's own shape.** One claim, one footnote, no figure. The footnote
names the source, the docx part, the element path, the view and the character
range; the finding line carries the claim's status (`user_attested`) and the
mark `[interpretation not machine-verified]`. The report declares itself a
first pass that is not journal-ready, and says that the Markdown, HTML and
DOCX forms are byte-reproducible while the PDF form is not.

## 3. The real model request

### 3.1 What the product's own CLI could not do

The product's only CLI route to a model is `roles run`. Run against the
pilot copy:

```
labcairn --workspace E:/labcairn-local/pilot-ws roles run \
  --role trajectory --project proj-pilot-002 --issue-key "pilot-paper-002:p[7]" --json
```

it refused:

```json
{"reason":"role_comment_not_in_the_chain",
 "message":"application refused (role_comment_not_in_the_chain): the chain holds no comment under the key 'pilot-paper-002:p[7]', and a judgement about a comment that is not there is invented"}
```

Exit code **3**, 5.96 s. The refusal is the product's own and it is right:
the loop judges what the chain holds, and the chain holds no comment for this
project. **So no command in the product's CLI can send a model request on
this copy** — not because the request would be refused, but because the only
surface that would send one never reaches the wire. That is a fact about the
CLI's shape, not a failure of the copy.

### 3.2 What the request was, and where it went

The request therefore went the way the earlier window's run went
([`LC-P4-PILOT-real-request-2026-11-25.md`](LC-P4-PILOT-real-request-2026-11-25.md)
§8): through the product's **application** layer, which is where the
consent gate lives. The driver for it is outside the repository — the
workspace's own `.local/round-e-evidence/driver/` directory — and it called
the product's own `request_model`, so the transmit check, the digest-bound
approval, the provider adapter and the exchange record are the product's.

**The prompt** was 877 characters, sha256 `9979f217…29ec98f`, and had three
parts: the model's instruction (suggest one replacement for a manuscript
passage), the statement this round recorded as evidence, and the anchored
passage itself — the 432 characters the claim is bound to, read out of the
product's own ledger, not re-extracted by the driver. The product's
redactor ran over it first and **changed nothing** (`scrub_changed_anything:
false`): the copy is desensitised, and no credential-shaped text is in it.

**The gates.** `permitted: true` — "permitted by grant
'grant-model-suggestions-pilot/LC-P4-PILOT', granted by 'owner' on
2026-11-24". The approval moved `granted` → `consumed` at
`2026-11-26T11:37:12.954588Z`, and the exchange landed at
`2026-11-26T11:37:23.460263Z`: **10.51 s** from the approval being spent to
the answer being recorded.

**The exchange**, as the provider's own usage block reported it:

| Field | Measured |
|---|---|
| Provider / model | `minimax` — the adapter's own provider string is `pydantic-ai:MiniMax-M3.1-Flash` — model `MiniMax-M3.1-Flash` |
| Attempts | 1 |
| Usage | input **505** tokens, output **1,750** tokens |
| Prompt digest | `7ccd2b2d…f980091a` (the adapter's own digest of what it sent) |
| Outbound | `prompt: true`, `tool_names: false`, `tool_arguments: true`, `document_excerpts: false`, `probe_prompts: true` |
| Observed at | `2026-11-26T11:37:23.458263Z` |
| Credential | fingerprint `d8053fe1…2dc9a7b` (a fingerprint; the key is in no file here and in no line of this record) |

`document_excerpts: false` is worth reading: the passage went out as part of
the prompt text, and the outbound audit says so rather than claiming a
document excerpt was attached.

### 3.3 The shape of the answer

The answer is **not** reproduced here. Its shape is:

- **483 characters**, one line, **12 sentences**, of which **314 characters**
  are CJK — the model rewrote the passage in the paper's own language rather
  than translating or echoing it.
- sha256 `c21799d6…e18d560`.
- The longest run of characters it shares with the passage it was given is
  **38** — it rewrote, it did not copy.
- Nothing checked it. No check ran on the answer, and the report this round
  did produce marks its own claim `[interpretation not machine-verified]` —
  which is the honest verdict for a statement no check has looked at, and the
  answer has had none.

### 3.4 What the answer did not become

The answer is not in the product's ledger as a proposal, a suggestion or a
guidance card. `review_suggestions` holds 0 rows, `guidance_checks` holds 25
rows — every one of them dated 2026-11-03, none from this round — and the
only `model_suggestion_runs` row for `proj-pilot-002` is the one the earlier
window's probe left, with `requests_made: 0`. **The product has no surface
that turns a raw model answer into a ledger entry** — the suggestion loop is
that surface, and it did not run (§4.1). So this round's model step is real,
paid for and recorded, but its result stops at the exchange record.

## 4. What this round could not exercise, and why

### 4.1 The suggestion loop — the copy has no comments

**The limitation.** This paper's copy carries **no Word comments and no
advisory annotations**. The advisor's marks are **113 tracked changes**
(the registration record's `revision_mark_count`), and the suggestion loop
reads **comment feedback** — `feedback_events`, keyed by issue key. For
`proj-pilot-002` that table holds **0 rows**.

**What the copy's marks look like in the product.** The ledger carries
revision **views** rather than marks: of the 268 addresses, **17 are
`rejected`** and 251 `accepted`, every one of them a paragraph or revision
block of `word/document.xml`. Those two numbers are not on the same scale
as 113 — the product addresses a paragraph and a revision block, the
registration counts a revision site — so this record does not read the
difference as a loss. The determinable fact is narrower and sufficient:
**the loop's input is a comment, this copy has none, and the loop refuses
to invent one** (the refusal message says exactly that).

**What this costs the pilot.** The pilot's exit gate `P4-G4` is about a
round on real material. On this copy, the part of the round that is
*advisor-driven* — read a mark, judge it, propose a revision, settle the
proposal — cannot run at all. The part that is *material-driven* — read the
paper, anchor a claim to it, ask a model for a rewrite of that passage,
render the report, export it — runs end to end, and this record is its
measurement.

### 4.2 The figure — the copy has no cells to select

The report's `figures` array is empty, and it is empty for a structural
reason rather than an oversight. The registered operators
(`labcairn.analysis.mean`, `…aggregate`, `…count`, `…sum`, `…min`, `…max`,
`…median`, `…stdev`) all take a **selection**: a source, named columns and a
row range. The copy's ledger holds **0 table-cell rows** — every one of its
268 addresses is a paragraph or revision block of `word/document.xml`. The
registered metadata says the document contains one table, but the product
does not extract table cells for it, so there is nothing for a column to be
selected from. `task figure` was therefore **not run**: there is no figure
this copy can carry, and the run would have been a refusal dressed as work.

### 4.3 The checks — a separate act, not run

The claim's verification log carries one C4 entry with `outcome: not_checked`,
because an attestation is a person standing behind a statement, not a check
of it. The product's C1/C2/C3 checks are separate commands and this round
did not run them; the report's own `[interpretation not machine-verified]`
marker is the honest statement of that.

### 4.4 The larger shape — one claim, one passage

This round carries **one** claim over **one** paragraph of an eighteen-page
paper. The report is a first pass over that claim, not a review of the paper.
Nothing here measures how the product behaves over a full manuscript's worth
of evidence.

## 5. The export

Six files per revision, written together, listed in the artifacts ledger with
`staleness: current` and the source's digest in the chain:

| File | Revision 1 (bytes / sha256) | Revision 2 (bytes / sha256) |
|---|---|---|
| `report.json` | 1,461 / `29c7dcef…0757d6c` | 1,465 / `3904ea81…4cf266c` |
| `report.md` | 952 / `39ee5f9d…fc77472df` | 957 / `6ae84f37…291b9cf20` |
| `report.html` | 2,026 / `b9db579b…79a2e044` | 2,030 / `a84790f3…38e01c3b6` |
| `report.docx` | 37,264 / `a38dc313…3bdcbe90` | 37,266 / `080309ad…9e101c302` |
| `report.pdf` | 2,539 / `0398f01b…f895ee511` | 2,541 / `997750a3…c99e1501` |
| `report-manifest.json` | 502 / `b11dc789…f01c70ab` | 502 / `2c47914e…af63d07c` |

Every digest above was computed twice — once by the product and written into
the receipt, once independently from the bytes on disk — and the two agree.
The artifacts table went from 0 rows to **12**.

## 6. Where the product's own bookkeeping stopped

These are measurements of this tree's behaviour, not defects claimed and not
defects ruled out.

1. **The suggestion loop's refusal left no event.** The `roles run` refusal
   (§3.1) is visible in the exit code and the message, and **absent from the
   event log**: the task's events for today run `seq 57 … 73` — seventeen of
   them — and hold no entry for it. A refusal that the log does not carry is
   a refusal only the operator who was watching can see.

2. **The approval stage stayed `blocked`, and the run stayed `running`.**
   The event chain for the request is complete and in the right order —
   `run_started` → `stage_entered` → `operation_awaiting_approval` →
   `approval_requested` → `stage_blocked` → `approval_granted` →
   `approval_consumed` → `operation_intent` → `model_exchanged` →
   `artifact_recorded` (twice, once per revision) — and it **ends there**.
   No `stage_completed`, no run finished. The approval stage still reads
   `blocked` although its approval was consumed and its request answered.
   The same is true of the requests the earlier window ran on 2026-11-25:
   this task now holds **nine** stages — eight `approval` stages and the
   `inventory` stage of this round — and **all eight approval stages read
   `blocked`**, while five of their approvals are `consumed` (four from
   2026-11-25, one from this round) and three are `granted` and unspent.
   **A model request that goes all the way through the gate does not close
   its stage.**

3. **A read wrote an event.** The first `task status --json` of this window
   left a `task_revised` event (`seq 57`, `2026-11-26T11:33:17Z`) — the
   product re-binds the task's material when it reports on the task, and a
   binding is a state change, so it is written. The log therefore holds one
   more entry than the number of things that changed.

4. **One earlier gap is closed.** The earlier window recorded two store rows
   for the copy's digest, one of them naming a path that no longer existed.
   The store now holds **one** row for this copy, `src-0ac499ea4d3a7d82`, at
   the path inside the grant's scope, and `ver-pilot-002-input` points at it.
   The version row is no longer an orphan.

## 7. Whether the product could carry a round on this copy

**On the material-driven half, yes.** The round ran: inventory bound the
copy's content hash as the stage's output; the addresses were listed and a
claim was recorded against one of them with three digests agreeing; the
consent gate asked, waited for a grant, and bound the grant to the
arguments' digest and to the policy's digest; a real model request went out
under the owner's signed grant and came back in 10.5 seconds with a token
count and a body; the claim was attested; the report rendered in two
revisions with the material's digest in the chain; and six files per
revision were written and listed. Every step went through the product's own
surface, and every number in this record was measured rather than asserted.

**On the advisor-driven half, no — and not because of the copy.** The
suggestion loop needs a comment, this copy has none, and the product is
right to refuse rather than invent a judgement about a mark that is not
there. The same refusal was reached by the earlier window's probe. The
pilot's own exit gate `P4-G4` therefore **cannot be evidenced by this
round**: what this round shows is that the product carries the *material*
round on a desensitised copy, and that the *marks* round needs a copy with
comments — or a product that reads tracked changes as the marks they are.

**And the CLI has no route to the model.** That is the sharpest thing this
round found. A round on a copy without comments can ask the model for
nothing through the product's own commands, because the only command that
would send a request refuses before the wire. The request in §3 went through
the application's layer, which is where the gate is, and it is the same layer
the service route uses — but it is not a command, and a pilot operator
following the quickstart would have no way to make it. Whether that is a gap
in the CLI or a deliberate boundary is the owner's call; this record only
states where the boundary is.

---

## 8. Where the material and the evidence are

- The pilot workspace: `E:/labcairn-local/pilot-ws` (unchanged in shape; the
  database is at revision `0032` and holds this round's records).
- The round's evidence — command outputs, the request's arguments, the
  prompt, the answer, the digests: the workspace's own
  `.local/round-e-evidence/` directory, **outside the repository**.
- The provider's configuration and the credential: in the workspace, outside
  this repository. **No key is in this record, and none is in the evidence
  directory.**
