# LC-P4-PILOT — one capability probe against the anthropic endpoint (2026-11-25)

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Date:** 2026-11-25.
**Tree:** `f52c7ae010781f7ec8010e7fd1baedc0faede33f`, Windows 11 Pro
(10.0.26300 x64, AMD64), Python 3.12.13.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. This record claims no acceptance for the pilot's step 3 — that step
still waits for the desensitisation checklist (§6).
**Authorisation:** the owner's signed record,
[`LC-P4-PILOT-model-authorisation-draft.md`](../plans/LC-P4-PILOT-model-authorisation-draft.md)
§1 (provider and model), §5 (timeout), §8 (run-record fields), and the
**owner's instruction on 2026-11-25** to probe this endpoint's
capabilities. The probe's prompt is the probe's own, and it carries
**none of the owner's material** (§3).

---

## 1. What was asked, and of what

| Field | Measured value |
|---|---|
| Endpoint (sanitised) | `https://api.minimax.cn/anthropic` |
| Protocol | `anthropic` |
| Model | `MiniMax-M3.1-Flash` |
| Endpoint fingerprint | `db47efa5986d25d9bae6a7d9788a5b0b7d5db0240a83c29aefb42ac0420f385c` |
| Credential | the operator's single-line key file, outside the repository; the value is in no file, no log and no record |
| Timeout | 60 seconds (the signed record's §5) |
| Observed at | `2026-11-25T02:58:02.480210+00:00` |
| Probes run | `structured_output_native`, `structured_output_prompted`, `tool_calls`, `usage_reporting` |
| Procedure | `scripts/provider_smoke.py` (the project's own; `python scripts/provider_smoke.py --dry-run` first, to confirm the configuration without sending) |

**The fingerprint is the same one the LC-P3-06 run measured on 2026-11-10
and the same one the LC-P2-18 run measured on 2026-10-28.** The three
runs therefore asked the same endpoint, the same model and the same
protocol, and the fingerprint is how a reader knows it.

## 2. What the endpoint answered

| Capability | Outcome | The evidence the probe recorded |
|---|---|---|
| `tool_calls` | **ok** | "a well-formed tool call naming the probe tool" |
| `usage_reporting` | **ok** | "a probe response carried a usage block" |
| `structured_output_prompted` | **ok** | "a bare JSON object validating against the probe schema" |
| `structured_output_native` | **unsupported** | "probe raised UserError" |

**Two of these differ from the reading of 2026-10-28, and the difference
is the reason this record exists.** The G5 acceptance record
(`docs/acceptance/G5-acceptance.md`) carried that earlier run's outcomes:
`tool_calls` ok, `usage_reporting` ok, `structured_output_native`
unsupported, and **`structured_output_prompted` unsupported** — the probe
raised a `KeyError` that day. Today the same endpoint, the same model and
the same protocol answer **`ok`**. So:

- **`structured_output_prompted` moved from unsupported to ok.** A
  capability that had been carried as "declined before a request is sent"
  now answers with a JSON object that validates against the probe's
  schema.
- **`structured_output_native` is still unsupported**, and still refuses
  before a request is sent.

**What the suggestion loop needs.** It sends a plain-text prompt and
reads a plain-text answer (`src/labcairn/application/model_suggestions.py`),
so it needs neither structured-output mode. What it does need is a
provider that answers at all — and the endpoint does.

**What a reader must not take from this.** A capability is measured
against **one endpoint, one model, one protocol, on one day**. A change
to any of the three invalidates it: the fingerprint is what says so.

## 3. What went out, and what did not

**The probe's own prompts.** Four probes, each asking the endpoint to do
something mechanical: emit a tool call, emit a JSON object against a
schema, report its usage. **No sentence of the owner's material, no
document excerpt, no pilot corpus text** was sent — the probe has no
access to any of it, and the pilot's step 3 has no registered excerpt to
send because the desensitisation checklist is unsigned.

**The repository's boundary held.** This record carries ids, a digest,
counts and a timestamp. It carries no key, no prompt body, no response
body, and no path to the key's file beyond the configuration's own name.

## 4. What it cost

**`Unknown(UNPRICED)`.** The provider's response carries no price, and
the project has no price table — the same answer LC-P3-06 carried until
it was priced on 2026-11-16. **A ceiling written from this record's
token count would be written from a number nobody has priced**, and the
one token figure that was measured elsewhere — 2,510 output tokens for a
372-character answer — says the number to spend against is an order of
magnitude larger than the answer it produces.

## 5. The probe's record is now stored by the product

**Corrected 2026-11-25, after the tenth batch.** This section first
recorded the opposite, and the opposite was true when it was written:
the probe answered, the answer was in this record, and **the product
persisted no probe record** — the only implementation of `ProbeCache`
was `InMemoryProbeCache`, and `doctor --probe` probed live and reported
without writing anything down, so the reading above was the only place
it existed.

**It is now stored.** The tenth batch made ADR-0002's promise real: a
probe record in the application-owned SQLite store, keyed on
`(endpoint_fingerprint, model, protocol)` and invalidated by a change to
any of the three (migration `0031_probe_records.py`,
`src/labcairn/application/probe_records.py`). **Verified on this
machine, on this endpoint**, against the anthropic route this record
names:

| what | before | after |
|---|---|---|
| `doctor` with no record | `declared, not probed`, every capability `unverified` | unchanged — an unprobed endpoint is still honestly unprobed |
| `doctor --probe` | probed live, reported, **wrote nothing** | probed live, reported, **and stored it** |
| `doctor` afterwards | still `unverified` — the measurement existed only in this document | **`probed, read back from the record of <timestamp>`**, with the four outcomes and their evidence |
| the stored row | — | `probe_records`: the endpoint fingerprint, the model, the protocol, the four outcomes, the evidence, the probes run, the observation time |
| a provider with `probed: false` | — | reports `declared unprobed by configuration`, every capability `unverified`, and **does not read the stored record or spend money even with `--probe`** |

The capability gate that refuses an endpoint with no probe record
(`src/labcairn/providers/bounded_run.py`) now reads what the product
stored, through the same cache the suggestion and role loops use. **The
honest fix the first version of this section asked for — a probe record
the product writes and the gate reads, rather than a record in a
document — is what this release carries.**

**What is still not established.** A probe record is a *floor*, not a
guarantee (ADR-0002's own words): it says the endpoint answered that
capability once, on one day, for a tiny schema. The consent question —
ADR-0006's *"a capability probe is not consent... a probe therefore
requires consent too"* — is **not** closed by this batch, and the probe
still issues its request without asking anyone. That is the next thing
this record would have to say, and it does not yet.

## 6. What this record does not claim

- **It does not claim the pilot's step 3 ran.** The desensitisation
  checklist's part-D result is unsigned, so no registered excerpt exists
  and there is no material to send.
- **It does not claim the spend is priced** (§4).
- **It does not claim multi-turn tool calling, retry, or cancellation over
  a real network** — the probe exercised none of them; that is the script's
  own disclaimer, and it stands.
- **It does not claim the capability persists beyond the endpoint,
  model and protocol it was measured on.** It does persist (§5), and the
  key is the invalidation: a change to any of the three means the stored
  record is not read.
- **It does not claim a probe needed anyone's consent** — ADR-0006 says
  it does, and the probe still asks nobody (§5).
- **It does not close a gate.** No gate row moves on the strength of a
  capability reading.

## 7. The evidence index (outside the repository)

`E:/labcairn-local/phase4-pilot-evidence/LC-P4-PILOT-capability-probe-2026-11-25/`

| what | where |
|---|---|
| the probe's own output, paste-ready | `probe-output.txt` |
