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

## 5. The probe's record is not stored by the product

**This is the finding worth carrying.** The probe answered, and the answer
is in this record — but **the product does not persist a probe record**.
`doctor` reports a capability as `unverified — no probe record for this
endpoint, model and protocol` because the only implementation of
`ProbeCache` in the tree is `InMemoryProbeCache`
(`src/labcairn/providers/probe.py`), and `doctor --probe` probes live and
reports without writing anything down. **So the reading above is the only
place it exists**, and a later `doctor` on this workspace will still say
`unverified` — not because the endpoint is unmeasured, but because
nothing writes the measurement down.

That matters for the pilot: the capability gate that refuses an endpoint
with no probe record (`src/labcairn/providers/bounded_run.py`) has nothing
to read on this workspace, and the honest fix is a probe record the
product writes and the gate reads — not a record in a document.

## 6. What this record does not claim

- **It does not claim the pilot's step 3 ran.** The desensitisation
  checklist's part-D result is unsigned, so no registered excerpt exists
  and there is no material to send.
- **It does not claim the spend is priced** (§4).
- **It does not claim multi-turn tool calling, retry, or cancellation over
  a real network** — the probe exercised none of them; that is the script's
  own disclaimer, and it stands.
- **It does not claim the capability persists** (§5).
- **It does not close a gate.** No gate row moves on the strength of a
  capability reading.

## 7. The evidence index (outside the repository)

`E:/labcairn-local/phase4-pilot-evidence/LC-P4-PILOT-capability-probe-2026-11-25/`

| what | where |
|---|---|
| the probe's own output, paste-ready | `probe-output.txt` |
