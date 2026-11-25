# LC-P4-PILOT — one real request under the signed authorisation

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Date:** 2026-11-25.
**Tree:** `ea2a7711bd4523b5f53930a6bbf75e6f4ca77d81` (worktree
`angry-poincare-b31569`), Windows 11 Pro (10.0.26300 x64, AMD64), Python
3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. This record claims no acceptance for the pilot's step 3 — that step
still waits for the desensitisation checklist (§5).
**Authorisation:** the owner's signed record,
[`LC-P4-PILOT-model-authorisation-draft.md`](../plans/LC-P4-PILOT-model-authorisation-draft.md)
(§1 provider and model, §2 scope and material, §3 request content, §4
budget, §5 timeout and retry, §6 substitute, §7 stop conditions, §9
signature), and the LC-P3-06 bounded-run precedent it names
([`LC-P3-06-real-half-2026-11-10.md`](LC-P3-06-real-half-2026-11-10.md)).
**Precedent followed:** the machine format is
[`LC-P4-PILOT-providers-config.md`](LC-P4-PILOT-providers-config.md); the
example in that document is the file this run went through.

**What is real here, and what is not.** The request is real: it went out
over the wire to the endpoint the signed record names, on the owner's paid
credential, and the provider answered with a token count and a body. What
is **not** claimed: that the pilot's step 3 has run (§5), that any
registered material was sent (§3), that a capability probe was made (§4),
or that the spend is priced (§5).

**The boundary this record obeys.** The repository stores ids, digests,
counts and durations — never request or response prose
(`LC-P4-PILOT-model-authorisation-draft.md` §8; G0 §4). So this document
carries no sentence of the prompt, no sentence of the answer, no key, and
no path of the key's file beyond the one the configuration names.

## 1. The run, as authorised

| Field | Measured value |
|---|---|
| Model | `MiniMax-M3.1-Flash` |
| Protocol | `anthropic` |
| Endpoint (sanitised) | `https://api.minimax.cn/anthropic` |
| Endpoint fingerprint | `db47efa5986d25d9bae6a7d9788a5b0b7d5db0240a83c29aefb42ac0420f385c` — **equal to the LC-P3-06 run's fingerprint of 2026-11-10**, so this is the same route that run used |
| Credential | `credential_file`, a single-line key outside the repository; fingerprint `d8053fe1b4c635e4903517299a3db2904be2943408a097d65262466d02dc9a7b`, no value recorded or printed |
| Timeout | 60 s (`timeout_s` in the configuration) |
| Budget | The signed record §4's fail-closed ceiling (100000 requests / 100000000 tokens); **1 request spent** |
| Retry policy | §5's: at most 3 consecutive failures, bounded backoff, retryable = network / timeout / 5xx. **1 attempt was needed** |
| Configuration | The file in `LC-P4-PILOT-providers-config.md` §6, digest `709e5a3bd9080847a5f2ecd1db288de1e28bb40e05c452a860e0d733da795684` |
| Sample class | `public_synthetic` — the LC-P3-06 precedent's own label for this class (§3) |
| Capability probe | **none** (§4) |
| Requests | **1** |
| Stop reason | none: the request succeeded on the first attempt |

**The dry reconciliation, before the spend.** The same driver was run
first against a local fake of the anthropic-compatible endpoint (a
throwaway HTTP server outside the repository): one request, one attempt,
outcome `success`, 41 input and 12 output tokens as the fake reported
them, 139 ms. The dry run's purpose was the request line, and it is
recorded in §4. The real run differs from the dry run in exactly two
objects: the endpoint and the credential.

## 2. The request, as measured

| Field | Value |
|---|---|
| Started at | 2026-11-25T01:26:20.084654+00:00 |
| Finished at | 2026-11-25T01:26:43.335638+00:00 |
| Wall clock, whole run | 23,251 ms |
| Wall clock, the request | 18,641 ms |
| Prompt | 469 characters, digest `251f3af6533a4da6c46bc39a57b32091a01d79c99968acebb881f4b5538d2955` |
| Prompt digest as the provider layer recorded it | `7e2699f73f12545ce6932d30f8f469624fa0d70352be5ea158e164576d305382` |
| Tokens in | **93** (`Known(93)`) |
| Tokens out | **2,510** (`Known(2510)`) |
| Tokens total | **2,603** |
| Answer | 372 characters, digest `91becccf26daa979bb6e3c484820bfdc2e23fcc278aabaa22c5fcb1af7aad4c4` |
| Answer accepted as a suggestion | yes — non-empty and not the passage verbatim, so the product's wrapper built one edit with the model as its author |
| Provider attempts | 1 |
| Cost | `Unknown(UNPRICED)` — the provider's response carries no price, and the pilot's §8 asks for the price basis or the same unknown, honestly |

**A note the owner should read before setting a token ceiling.** The
provider reported **2,510 output tokens for a 372-character answer**. The
product read one answer of 372 characters; the provider's own usage block
counts tokens the product never sees. The obvious candidate is a reasoning
model's reasoning tokens, **which this run did not measure**. What it
measured is that the number the budget will be spent against is an order of
magnitude larger than the answer it produces, so a ceiling written from
"answers of a few hundred characters" would be written from the wrong
number.

**The answer's body is outside the repository.** It is stored, with the
driver and the record, in the evidence directory named in §6, for a person
to read. It contains nothing of the owner's material, because nothing of
the owner's material was sent (§3).

## 3. The material that was sent, and why it was synthetic

**What went out.** Two pieces of text, written for this run: one reviewer
comment of 114 characters and one anchored passage of 190 characters, both
general scientific prose about chlorine disinfection in a batch reactor.
Nothing else: no name, no affiliation, no project number, no funding text,
no acknowledgement, and **no sentence of the owner's material** — the
anchored passage's digest is of a sentence written in this run.

**Why synthetic, and not an excerpt of the pilot paper.** The signed
record's §2 permits *"the desensitised copy registered by the desensitisation
checklist and its excerpts only"*. The checklist
([`LC-P4-PILOT-desensitisation-checklist.md`](../plans/LC-P4-PILOT-desensitisation-checklist.md))
is still `DRAFT`: its part-D result — the one that registers the copy's
digest and metadata — is unsigned, and the document says so in its own
header: *"Until the owner has signed that result, the import step (plan §9.2
step 2) must not run and no copy enters the pilot."* **So no registered
excerpt exists to send**, and sending a paragraph from an unregistered copy
would have been the owner's material going out under a desensitisation that
nobody has confirmed. The signed record names the LC-P3-06 precedent's own
restriction on supply — *"Q6: synthetic/sanctioned samples first; the real
advisor sample stayed a named gap"* — and this run took the same road.

**The real advisor sample stays a named gap.** It is the first thing the
pilot's step 3 should send, and it cannot be sent until the checklist is
signed and the record's `subject_ref` names the registered copy.

**What the run therefore proves, and what it does not.** It proves the
route, the model, the credential, the timeout, the token accounting and
the suggestion wrapper all work end to end on the authorised endpoint. It
does **not** prove that the owner's material can be sent: that is the
checklist's job, and it is unsigned.

## 4. The two things nobody had checked

### 4.1 The base URL needs no trailing path element — and a `/v1` would be doubled

**Measured.** The Anthropic client is handed the base URL as configured and
appends `/v1/messages` to it. Against a local fake, with
`base_url = http://127.0.0.1:8932/anthropic`, the request line was:

```
POST /anthropic/v1/messages?beta=true
```

So `https://api.minimax.cn/anthropic` is the **whole** route: the endpoint
the record names needs no trailing element, and the run's success confirms
it against the real host. The `?beta=true` is pydantic-ai's doing — its
Anthropic model calls the client's **beta** endpoint, and the beta
namespace is what puts the query flag on the request line.

**The same measurement found a defect in the other direction.** A base URL
ending in `/v1` is **doubled**: `https://api.anthropic.com/v1` composes to
`https://api.anthropic.com/v1/v1/messages`. And LabCairn's own default
anthropic base URL carries that `/v1`
(`src/labcairn/providers/credentials.py:75-78`,
`DEFAULT_BASE_URLS[ANTHROPIC] = "https://api.anthropic.com/v1"`), which
`effective_base_url` returns whenever an `anthropic` entry leaves `base_url`
empty (`credentials.py:176-178`). **So an `anthropic` provider entry must
name its `base_url` explicitly, and that base URL must not end in `/v1`** —
otherwise the request goes to a path that does not exist. The authorised
entry names it, and names it correctly; the defect is in the default only,
and it is unreached by any configuration this record covers. **It is a
finding for the owner, not for this window**: the default is another
window's file (`src/labcairn/providers/`), and this record does not change it.

### 4.2 The capability probe is not a gate on the suggestion path — and nothing stops an unknown endpoint

**Measured in the code.** The suggestion transport builds its adapter with
**no** `required_capabilities` (`src/labcairn/cli/commands.py:2623-2630`),
and the adapter's capability gate returns immediately when that set is
`None` (`src/labcairn/providers/adapter.py:476-478`). So:

- the G5 measurement that this supplier's `structured_output_native` and
  `structured_output_prompted` are **unsupported** does not block this
  path, and
- **the same silence means nothing stops an unknown endpoint before a
  request goes out.** No probe record is consulted, no route is checked,
  and the request's own failure is the first sign that the endpoint is
  wrong. This run carried no probe record at all and still went out.

**That is the right shape for this path, and the reason is the path's
request shape.** The suggestion path sends a plain-text prompt and reads a
plain-text answer (`src/labcairn/application/model_suggestions.py:148-173`,
`301-313`), so it needs no structured output and no tool support — it
asked for none. The cost of that correctness is the one named above: **a
wrong `base_url` is discovered by a failed request, not by a refusal.** The
configuration's own refusals (§8 of the format document) are about *shape*;
a route that answers is a route that spends.

**What the LC-P3-06 precedent did about it, and what this run did.** That
run made no new probe either — Q1 and Q2 named the already-probed route,
and the capability record it used was the 2026-10-28 one the release notes
record. This run made **no probe and carried no capability record at all**,
which is a weaker position than LC-P3-06's, and it is the honest one to
state: the path does not require one, so spending one would have been a
probe nobody asked for.

## 5. What this record does not claim

- **It does not claim the pilot's step 3 ran.** Step 3 needs a workspace
  with the registered copy, pending opinions, digest-bound approvals and a
  per-item human approval flow. This run sent one synthetic passage
  through the provider layer and the suggestion wrapper; it spent no
  approval, because there is nothing yet to spend one on.
- **It does not claim the suggestion loop's own gates were exercised.** The
  request went out through the provider layer's adapter with the consent
  port carrying the loop's decision
  (`src/labcairn/cli/commands.py:2726-2742`) — the shape the wiring uses
  when the loop has already spent its approval. The pilot's transmit gate
  and its approval spend have not been exercised against a real material.
- **It does not claim the spend is priced.** `Unknown(UNPRICED)`, the same
  answer LC-P3-06 carried until it was priced on 2026-11-16.
- **It does not claim the capability record was re-measured** (§4.2).
- **It does not claim the real advisor sample was sent** (§3).
- **It does not claim the substitute path was exercised.** The signed
  record's §6 names `substitute-model` as the labelled fallback; no retry
  was needed, so no fallback ran.

## 6. The artefacts, and one thing the owner must fix

**The artefacts live outside the repository**, at
`E:/labcairn-local/phase4-pilot-evidence/LC-P4-PILOT-real-request-2026-11-25`:
the driver (`driver/one_request.py`), the local fake used for the dry
reconciliation (`driver/fake_endpoint.py`), the configuration the run read
(`providers.json`), the machine-readable record (`run-record.json`), and
the answer body (`answer.txt`). The key's value appears in none of them —
checked mechanically, not by eye.

**The workspace that already exists names the wrong route.** The
pilot workspace's own `providers.json` names
`E:/labcairn-local/secrets/minimax-key.txt`, which LC-P2-18's record calls
**retired** ("the old `minimax-key.txt` is retired", and the first key
of the operator's newer three-line file is the one that probed `ok` — see
`docs/acceptance/LC-P2-18-live-run.md` §2).

**Corrected 2026-11-25, by measurement: the key is not the problem.**
The two files were compared by the providers layer's own credential
fingerprint — the digest `Credential.of` computes over the stripped
value, which is what the layer uses to say which two configurations
share a key:

| file | bytes | fingerprint |
|---|---|---|
| `minimax-key.txt` | 126 | `d8053fe1b4c635e49035…` |
| `minimax-m31-flash-active.txt` | 125 | `d8053fe1b4c635e49035…` |
| `minimax-m31-flash.txt` (the three-line file) | 270 | `6faaff29b74d13092902…` |

**The first two hold the same key**, so what was retired is a *name*, not
a secret: the file the workspace names carries the key that the
three-line file's first line carried and that this run used successfully.
The three-line file is a different key, and it is the one LC-P2-18 did
not probe. **A request against the workspace's file as it stands would
therefore not fail on the credential** — it would go to the wrong place.

**What is wrong with it is the route, the protocol and the grant.** The
workspace names the `openai_compatible` protocol at
`https://api.minimax.cn/v1` with a 120-second timeout, where the signed
2026-11-24 record names the `anthropic` protocol at
`https://api.minimax.cn/anthropic` with 60 seconds; and the workspace
carries **no `model_suggestions` grant at all** — eight fields where the
signed record names eight values, and the authorisation gate refuses the
whole thing unless every one of them is filled. **The suggestion loop
against that workspace is not merely misrouted; it is unauthorised.**

Replacing that file with the configuration in
`LC-P4-PILOT-providers-config.md` §6 is the owner's next step, and it is
a one-file edit outside the repository. It is a grant and a route that
change, not a key that has to be re-issued.

## 7. The named gaps this run leaves, in the order they close

1. **The desensitisation checklist's part-D result is unsigned**, so no
   registered excerpt exists and the pilot's step 3 has no material to
   send. **Owner.**
2. **The workspace's `providers.json` names the wrong route and carries no
   grant** (§6). The credential it names is the same key the run used, so
   what has to change is the protocol, the endpoint, the timeout and the
   eight `model_suggestions` fields — not the key. **Owner.**
3. **No capability probe has been made against the anthropic route** since
   2026-10-28, and the suggestion path does not require one (§4.2).
   **Not blocking.**
4. **The spend is unpriced** (§5). **Owner, before a budget is set.**
5. **The output-token accounting is larger than the answer it produces**
   (§2), and the reason is not measured. **Owner, before a ceiling is set.**

## 8. The second round — the imported copy, and the gate

**Date:** 2026-11-26 (the run itself is on the night of 2026-11-25 UTC).
**Tree:** `5a4e4587d076f1e934df86ed6a00e6126981fcc0` (worktree
`pilot-import-request-0745db`).
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Companion record:**
[`LC-P4-PILOT-import-2026-11-25.md`](LC-P4-PILOT-import-2026-11-25.md).

Sections 1–7 above are the first round and are left as they were written.
This section is the second run under the same signed authorisation.

### 8.1 What is new here, and what is the same

**New.**

- **The material.** The request carries excerpts of the *registered
  desensitised copy* (`pilot-paper-002`, digest `04cc31be…a6172d`), imported
  into the pilot workspace through the product's own `sources ingest`. The
  first round sent two sentences written for the run, because the checklist
  was then DRAFT.
- **The checklist is signed**, so the material is the signed copy and the
  import ran against it.
- **The consent gate was exercised.** Each request spent a digest-bound
  approval and passed the transmit gate; one request inside the boundaries
  was sent, one outside them was refused with the approval left unspent and
  nothing sent.
- **The ceiling comes from the provider's own usage report**, not from an
  answer's length.

**The same.** The endpoint, model, protocol, timeout, credential
fingerprint, destination, grant id, subject ref, scope, budget and retry
policy are the ones §1–§3 name. The machine format is the §6 example, with
the one change §8.4 explains. The boundary is the same too — ids, digests,
counts and durations; no prompt prose, no answer prose, no key.

### 8.2 The request's shape, and where its material came from

The prompt is the product's own template with the reviewer-comment section
dropped, because the copy carries no comments (import record §6):

```
You are suggesting one replacement for a manuscript passage.
Anchored passage:
{excerpt}
Reply with the replacement text for the passage, and nothing else.
```

| Field | Value |
|---|---|
| Excerpt's provenance | the accepted view of the imported copy, digest `04cc31be…a6172d` — 1,539 characters read from the product's own `source_texts` rows (251 accepted rows for that digest) |
| Scrubbing | the product's `Redactor`; **0 characters changed** — nothing credential-shaped was in the excerpt |
| Prompt length | 1,699 characters |
| Prompt digest (this record) | `3ea976c476ca58479550b2e53a630ee8bb1ad0f4de71b6deb35269e4d7981b75` |
| Prompt digest (provider layer) | `895e8eb8a3d1b9a6e97860a1c9b4821c9d412c7b6fe3dafa39a8147452716bef` — the same value in every request of this round |
| Material reference | `pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` — the imported source's root-relative key |
| Subject | `pilot/LC-P4-PILOT/desensitised-copy` |
| Destination | `https://api.minimax.cn/anthropic` |
| Provider / model / protocol / timeout | `minimax` / `MiniMax-M3.1-Flash` / `anthropic` / 60 s |
| Credential | fingerprint `d8053fe1…dc9a7b` (§1) |
| Grant | `grant-model-suggestions-pilot/LC-P4-PILOT`, scope `pilot/LC-P4-PILOT/desensitised-copy/**` |

Three permitted requests were made, each with its own digest-bound
approval:

| Round | Approval | Gate | Answer | Provider's reported usage (in / out) | Duration |
|---|---|---|---|---|---|
| A — measuring | `01a213fc-36f0…` | permitted; approval **consumed** | 1,666 characters, digest `94af4c82…` | `Known(1)` / `Known(6089)` | 34.64 s |
| B — under the ceiling the report gives | `01a213fc-bede…` | permitted; approval **consumed** | 1,780 characters, digest `4eeaa1a3…` | `Known(1)` / `Known(2231)` | 23.65 s |
| D — a second reading | `01a213fd-c3a2…` | permitted; approval **consumed** | 1,546 characters, digest `fb68f086…` | `Known(1)` / `Known(3000)` | 34.32 s |

### 8.3 The gate: inside the boundaries allowed, outside them refused

**Inside.** The transmit check returned `permitted = True` — the consent
layer's own decision, naming the grant, the permission `external_transmit`,
the purpose `transmit`, the destination, and the owner who granted it on
2026-11-24. The approval was consumed, the request went out, the provider
answered, and the exchange landed in the event log (`01a213fc-be4b-…` for
round A).

**Outside.** The same request shape, the same subject, the same destination
— with the material reference pointing at `batch10-v01-main.doc`, a corpus
file that exists in the workspace and is **not** under the grant's scope:

```
application refused (consent_scope_not_covered): grant
'grant-model-suggestions-pilot/LC-P4-PILOT' covers 'batch10-v01-main.doc' for
'external_transmit', but its scope 'pilot/LC-P4-PILOT/desensitised-copy/**' does
not reach this material. The remedy is a grant whose scope covers it.
```

Measured after the refusal:

| | |
|---|---|
| The approval's state | **`granted`** — not consumed |
| Exchange records | **none** — nothing was sent |
| The wire | never reached |

That is the order the repository's own bridge holds: the transmit check runs
**before** the approval is spent, so a request refused for want of a grant
leaves the approval unspent and sends nothing.

### 8.4 The token ceiling, from the provider's own report

**The first round's warning was right, and is now measured.** The first
round saw a 372-character answer and a provider report of 2,510 output
tokens (≈6.7 tokens per character). Three readings of one prompt in this
round:

| Round | Answer characters | Provider's reported output tokens | Tokens per character |
|---|---|---|---|
| A | 1,666 | 6,089 | 3.65 |
| B | 1,780 | 2,231 | 1.25 |
| D | 1,546 | 3,000 | 1.94 |

The factor is **not a constant**: it moves between 1.25 and 3.65 on the same
prompt, and between 1.25 and 6.75 across both rounds. A ceiling written
from an answer's length is written from a number that varies by nearly a
factor of three, and it is not the number the provider reports.

**The ceiling this run used, and where it came from.**

- Per request, the output ceiling was **`max_output_tokens = 6,089`** — the
  provider's own reported output tokens for round A, and the largest of the
  three figures measured. No character count appears in it.
- Per run, the token ceiling was `RunBudget(max_total_tokens=Known(6090))`,
  with the ledger carrying round A's measured usage (`Known(1)` in,
  `Known(6089)` out). The pre-flight measured that ceiling, found it
  satisfied, and the request went out. The ceiling was enforceable because
  the provider reports usage at all.
- **The input side of the provider's report cannot be used.** It reads
  `Known(1)` for a prompt of 1,699 characters. Whatever that field counts
  at this endpoint, 1 is not the size of this prompt, so "input + output"
  taken from this report would under-read the traffic that was sent by more
  than a thousand tokens. The ceiling is therefore anchored on the output
  side, and the input side is carried as what the operator can state — the
  prompt's 1,699 characters — not as the provider's number.

**Why a ceiling had to be set at all.** The first attempt of this round
used the product's own CLI assembly, which passes no output ceiling, and the
provider's answer reached **its** output ceiling: the product refused the
answer (`ProviderOutputTruncatedError`) rather than record a truncated answer
as one. That refusal is the product behaving correctly; the gap is that the
operator had nowhere to put a ceiling (§8.5, fact 1).

**The variance is the practical finding.** Three readings of one prompt
differ by 2.7× (2,231 → 6,089). A ceiling equal to a single reading is a
bet; the largest of three is better and still not a bound. **A pilot that
sets one output ceiling for a run of requests needs the largest figure the
provider has reported, and needs to read a refusal as a measurement rather
than as a failure.**

### 8.5 Three facts about the product this run turned up

1. **The CLI's wiring passes no output ceiling, and the authorisation record
   has nowhere to put one.** `_suggestion_transport` builds
   `PydanticAiModelProvider` without `max_output_tokens`
   (`src/labcairn/cli/commands.py:2889`), and `MODEL_SUGGESTIONS_FIELDS` is
   a closed set of eight fields — `provider`, `destination`, `subject_ref`,
   `granted_by`, `granted_at`, `expires_at`, `scope`, `grant_id`
   (`src/labcairn/cli/commands.py:136`) — with no output limit among them.
   So the product's suggestion path runs under the provider's default output
   ceiling, and a long answer is refused as truncated instead of being asked
   for shorter. This round had to assemble the transport itself — the
   product's own `build_model`, `PydanticAiModelProvider`, `make_sniffer`
   and `_ProviderTransport`, with that one argument added — to run under a
   ceiling at all. **A finding for the owner; this record changes no code.**
2. **The provider's usage report is not symmetric.** Output tokens are
   plausible (3,000–6,089 for answers of 1,546–1,780 characters); input
   tokens read `1` for every request, including a 1,699-character prompt.
   Any ceiling or budget that reads "input + output" as the traffic would be
   wrong by more than a thousand tokens per request against this endpoint.
3. **The suggestion loop's own `max_tokens` is an estimate, not a
   measurement.** `SuggestionLoop._check_token_budget` compares
   `_tokens_total()`, which sums `tokens_estimated`
   (`src/labcairn/application/model_suggestions.py:1058` and `:1094`), while
   the provider's own report sits in the exchange record and the run row
   does not use it. The loop's ceiling is therefore still written from
   something that is not the provider's number — the defect §8.4 names, one
   layer further in.

### 8.6 What the pilot's own suggestion loop can ask about the imported copy: nothing

The product's suggestion loop is the pilot's step-3 surface
(`POST /review/suggest`, mode `real`). It was run over the imported copy's
version in real mode, against the same grant, the same transport and the
same ceiling:

| | |
|---|---|
| Project / version | `proj-pilot-002` / `ver-pilot-002-input` |
| Requests made | **0** |
| Opinions skipped | 0 |
| Suggestions recorded | 0 |
| Stopped because | nothing — the run had no opinion to ask about |

The reason is the material's: the copy carries **no Word comments** (0
`commentRangeStart`, no `word/comments.xml`), and its advisor's marks are 113
tracked changes. The loop walks comment feedback events, so for this copy it
has no opinion, and it spends no approval and sends nothing. The import
record's §6 measures the same fact from the file side.

**So the request this round made was not a suggestion about an opinion.** It
was one request carrying desensitised excerpts of the imported copy, made
through the product's own model-request bridge (`request_model` — the bridge
the roles path and the claim-extraction path use), under the signed grant,
with the excerpts read from the ledger the import wrote. That is the honest
description of what the pilot's first real request was.

### 8.7 The answers are not quoted, and cannot be

The model reproduced the material: the longest run of characters the round-D
answer shares with the excerpt it was given is **70 characters**. A copy of
the manuscript therefore sits inside the model's answer, which is why this
record carries digests and character counts and no prose — and why the
answer text was not written to the repository. It was not written to the
evidence directory either: the run compared the two texts by measurement and
reported the number.

### 8.8 Evidence

| What | Where |
|---|---|
| The run record (ids, digests, counts, usage) | `E:/labcairn-local/phase4-pilot-evidence/LC-P4-PILOT-real-request-2026-11-26/run-record.json` |
| The third request and the loop probe | `E:/labcairn-local/phase4-pilot-evidence/LC-P4-PILOT-real-request-2026-11-26/run-record-round-d.json` |
| The driver (outside the repository) | `…/LC-P4-PILOT-real-request-2026-11-26/driver/run_request.py`, `…/driver/run_round_d.py` |
| The workspace's provider configuration (outside the repository) | `E:/labcairn-local/pilot-ws/providers.json` — the §6 example, which replaces the file the first round found naming the wrong route (§7, gap 2) |
| The ledger | `E:/labcairn-local/pilot-ws/labcairn.db` — `approvals` (consumed, and unspent), `events` (the exchange records), `access_grants` (`grant-model-suggestions-pilot/LC-P4-PILOT`), `model_suggestion_runs` |
| The import | [`LC-P4-PILOT-import-2026-11-25.md`](LC-P4-PILOT-import-2026-11-25.md) |

### 8.9 The gaps, after this round

1. **Closed — the checklist's part-D result was unsigned.** The checklist is
   signed, the copy is registered, and the copy has been imported (import
   record §1–§4).
2. **Closed — the workspace's `providers.json` named the wrong route and
   carried no grant.** The file now names the authorised route and carries
   the grant, the grant is registered in the store, and the gate has
   permitted and refused for real (§8.3).
3. **Open — the output-token accounting is unexplained on the input side**
   (§8.5, facts 2 and 3): the provider reports `Known(1)` input tokens for a
   1,699-character prompt, and the loop's ceiling is still an estimate.
   **Owner, before a budget is set.**
4. **Open — there is nowhere to put an output ceiling** (§8.5, fact 1): the
   closed `model_suggestions` record has no field for it, so the product's
   own wiring cannot run under one. **Owner.**
5. **Open — the pilot's step 3 still has no opinion to work on.** The
   material's advisor marks are tracked changes, and the loop reads
   comments (§8.6). Until a version of the copy carries comments, or the
   loop learns to read revision events, the pilot's suggestion surface has
   nothing to suggest about. **Owner — this is the pilot's first structural
   finding.**
