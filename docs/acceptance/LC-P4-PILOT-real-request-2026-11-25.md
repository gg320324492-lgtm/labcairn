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

**The workspace that already exists points at a retired credential.** The
pilot workspace's own `providers.json` names
`E:/labcairn-local/secrets/minimax-key.txt`, which LC-P2-18's record says
is **retired** ("the old `minimax-key.txt` is retired", and the first key
of the operator's newer three-line file is the one that probed `ok` — see
`docs/acceptance/LC-P2-18-live-run.md` §2). That workspace also names the
`openai_compatible` route at `https://api.minimax.cn/v1` with a 300-second
timeout, which is **not** the configuration the signed 2026-11-24 record
names. **A request run against that file as it stands would carry the
retired credential and the wrong route.** Replacing it with the
configuration in `LC-P4-PILOT-providers-config.md` §6 is the owner's next
step, and it is a one-file edit outside the repository.

## 7. The named gaps this run leaves, in the order they close

1. **The desensitisation checklist's part-D result is unsigned**, so no
   registered excerpt exists and the pilot's step 3 has no material to
   send. **Owner.**
2. **The workspace's `providers.json` names the retired credential** (§6).
   **Owner.**
3. **No capability probe has been made against the anthropic route** since
   2026-10-28, and the suggestion path does not require one (§4.2).
   **Not blocking.**
4. **The spend is unpriced** (§5). **Owner, before a budget is set.**
5. **The output-token accounting is larger than the answer it produces**
   (§2), and the reason is not measured. **Owner, before a ceiling is set.**
