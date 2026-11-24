# LC-P4-PILOT — real-model authorisation record (signed)

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Status:** `AUTHORISED — all fields filled from the owner's 2026-11-24 choices and signed in §9; real requests are permitted only within the scope and limits below.`
**Boundary source:** [`LC-P4-G0-baseline-freeze.md`](LC-P4-G0-baseline-freeze.md)
§5 (real-model service boundary).
**Precedent:** the LC-P3-06 bounded-run authorisation
([`../acceptance/LC-P3-06-real-half-2026-11-10.md`](../acceptance/LC-P3-06-real-half-2026-11-10.md)),
which was gated on
[`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §4.9 and the seven
answers of 2026-11-09, ran on the owner's paid credential, counted
5,136 / 50,000 authorised tokens, and recorded what was real and what was
not before the first request went out.

**How to confirm (confirmed 2026-11-24).** All fields in §1–§7 are filled from the owner's
2026-11-24 choices. The signature in §9 is written; this record is the
authority P4-CAP's real-model step and the pilot's step 3 run against.
The signed record is what P4-CAP's real-model step and the pilot's
step 3 run against, per §9. **Real requests are permitted only inside
the provider, material, budget, timeout and stop boundaries recorded
below; anything outside them stays refused, and the substitute path is
the labelled fallback when retries are exhausted.**

G0 §5 requires the owner to authorise the real model *before P4-CAP's
real-model step runs*, in the style of the LC-P3-06 bounded-run
authorisation. This draft lays out every field that record must carry.
The owner fills each field; the filled record is what P4-CAP's model step
and P4-PILOT's trial run against. **No request is sent against an
unfilled field** — an unfilled field means the step it gates does not run.

**Where the plan's wording this record carries was read.** §7's stop
conditions and §2's scope are the plan's own requirements carried into
English; they were read from
[`PHASE_4-execution-plan.md`](PHASE_4-execution-plan.md) **Read
2026-11-25**, and the section numbers say where each one lives.

## 1. Provider and model

| Field | Owner to fill | Notes / precedent |
|---|---|---|
| Provider name | MiniMax (per LC-P3-06 bounded-run precedent) | The service or vendor the credential belongs to |
| Model id | MiniMax-M3.1-Flash; same-series aliases pre-authorised, actual id recorded per request | The exact model identifier the pilot calls — the id recorded per request, not a marketing name |
| Endpoint / access route | https://api.minimax.cn/anthropic (protocol: anthropic), per LC-P3-06 | API base, deployment name, or gateway path, as the record that lets a later reader reproduce what was called |
| Credential holder | Owner (prepaid token plan, credential file outside the repository) | Whose credential pays — the LC-P3-06 run was paid by the owner's credential and says so in its record |
| Authorised model versions/aliases | Same-series arbitrary versions pre-authorised; each request records the actual model id | Whether fallback aliases of the *same* provider are pre-authorised, or every change re-opens this record |

## 2. Purpose and scope

| Field | Owner to fill | Notes / precedent |
|---|---|---|
| Purpose | Per-item revision suggestions on the desensitised pilot paper and multi-source rule-distillation candidates; no autonomous apply, no publication text, candidate rules require mentor confirmation | Expected: generating revision suggestions on the desensitised pilot paper for human per-item approval — not autonomous application, not publication text |
| Scope of use | Pilot §9.2 step 3 and the multi-source distillation path only; everything else out of bounds | Which pilot tasks/stages may call the model (plan §9.2 step 3); everything outside the named scope is out of bounds |
| Permitted input material | Desensitised paper excerpts with advisor comments, trajectory cases, and desensitised PPT/meeting excerpts; no names, affiliations or project numbers | Expected: the desensitised copy registered by the desensitisation checklist ([`LC-P4-PILOT-desensitisation-checklist.md`](LC-P4-PILOT-desensitisation-checklist.md)) and its excerpts only — the LC-P3-06 precedent restricted supply the same way (Q6: synthetic/sanctioned samples first; the real advisor sample stayed a named gap) |
| Prohibited uses | No names/affiliations/project numbers/funding text; no material outside the pilot paper; no model output recorded as the human author of a suggestion | Expected: no names/affiliations/project numbers in any request; no material outside the pilot paper; no use as the recorded author of suggestions (suggestions are stored separately from human approvals, plan §7.2) |
| Authorisation window | 2026-11-24 to 2026-12-24 (30 days; review on expiry) | Start date and expiry or review date; expired authorisation stops the model step |

## 3. Request content boundary

| Field | Owner to fill | Notes / precedent |
|---|---|---|
| What may be sent | Only the desensitised passage a suggestion needs (whole paragraph / fixed window), plus the trajectory, PPT and meeting excerpts named in §2; each sent as digest-bound excerpt refs | Per G0 §5: only the desensitised manuscript excerpts a suggestion needs. Owner confirms the excerpting rule (whole passage / fixed window / section) |
| What may never be sent | Names, affiliations, project numbers, funding text, acknowledgements, and any material outside the pilot paper (G0 §5) | Names, affiliations, project numbers, funding text, acknowledgements, and any material outside the pilot paper (G0 §5) |
| Pre-send screening | Operator checks each outgoing excerpt against the desensitisation checklist A-item patterns; result lands in the request record | Who/what checks each outgoing excerpt against the A-item patterns of the desensitisation checklist before the request leaves; the check result lands in the request record |
| Excerpt provenance | Each excerpt logged by source locator + digest; no content copies in the repository (G0 §4) | Each excerpt is logged by source locator + digest (no content copies in the repository, G0 §4 boundary) |

## 4. Budget

| Field | Owner to fill | Notes / precedent |
|---|---|---|
| Total token ceiling for the pilot | No hard ceiling: fail-closed fields configured at 100000 requests / 100000000 tokens; stop by timeout, consecutive failures and cancellation | The pilot sets its own ceiling in this record (G0 §5). Precedent: LC-P3-06 was authorised for 50,000 tokens and used 5,136 |
| Per-request token cap | No hard cap; request size bounded by the desensitised excerpt selection | Cap on a single request's input+output tokens; a request that would exceed it is trimmed or refused before sending |
| Per-batch accounting | Tokens counted and recorded per request batch (G0 §5) | Tokens are counted and recorded per request batch (G0 §5) |
| On budget exhaustion | Fail-closed stop, stop reason budget-exhausted, remaining work waits for the owner | Expected per G0 §5: the loop stops, the stop reason `budget-exhausted` is recorded, and remaining work waits for the owner |

## 5. Timeouts and error classification

| Field | Owner to fill | Notes / precedent |
|---|---|---|
| Request timeout | 60 seconds per request | Every model call carries a timeout (G0 §5); owner sets the seconds |
| Retryable classes | Network errors, timeouts, 5xx | G0 §5's default: network errors, timeouts, 5xx. Owner confirms or amends |
| Non-retryable classes | Refusal (policy decline) and authentication failure, classified at the call boundary | G0 §5's default: refusal (policy decline) and authentication failure, classified at the call boundary. Owner confirms or amends |
| Retry policy | Up to 3 consecutive failures, bounded backoff; stop after 3 | Backoff with a bounded count (G0 §5); owner sets the count and backoff base |
| Error record granularity | Failures, refusals and stop reasons recorded per call | Expected per plan §7.2: failures, refusals and stop reasons are recorded per call |

## 6. Fallback / substitute model

| Field | Owner to fill | Notes / precedent |
|---|---|---|
| Substitute model id | substitute-model (existing labelled stand-in) | The fallback the loop offers when retries are exhausted (G0 §5; plan §7.2: retry and substitute-switch are the two paths on real-model failure) |
| Switch condition | Retries exhausted, or owner explicit switch instruction mid-run | Expected: retries exhausted, or owner's explicit switch instruction mid-run |
| Labelling rule | Substitute output labelled substitute, never recorded as the real model result | Expected per plan §7.2: substitute output is labelled as substitute and **never recorded as the real model's result** |
| Substitute authorisation | Runs under this record only as a labelled fallback; spends no real-model budget | Whether the substitute runs under this same record or needs its own authorisation (provider, budget, scope) |

## 7. Stop conditions

The loop stops, and the run record names which stop fired (G0 §5):

| Stop | Owner to fill | Notes |
|---|---|---|
| Budget exhausted | confirm / amend | §4's ceiling reached |
| Repeated refusal | confirm / amend | Owner sets the refusal count that triggers the stop |
| Owner cancellation | confirm / amend | Owner may stop the run at any point; the stop reason is recorded |
| Other | No additional pilot-specific stop; full fail-closed set above | Any pilot-specific stop the owner wants (e.g. wall-clock limit on the trial session) |

## 8. Run-record fields

Every model call and every batch writes these fields (plan §7.2, G0 §5,
LC-P3-06 precedent). The repository stores ids, digests, counts and
durations — never request/response prose (G0 §4 boundary):

| Field | Notes |
|---|---|
| `request_id` / `batch_id` | Links calls that belong to one batch |
| `task_id`, `opinion_id` | The pilot data model's trace ids (G0 §6) |
| `model_id`, `provider` | As authorised in §1; substitute calls carry the substitute id and the `substitute` label |
| `input_excerpt_refs` | Source locator + digest per excerpt sent (no content) |
| `tokens_in`, `tokens_out`, `tokens_total` | Counted per request and per batch |
| `duration_ms`, `started_at`, `finished_at` | Timing |
| `outcome` | `success | timeout | network-error | 5xx | refusal | auth-failure | cancelled` |
| `retry_count`, `retryable` | Per the §5 classification |
| `fallback_used` | Whether a substitute produced the output |
| `stop_reason` | Set on the run when a §7 stop fires: `budget-exhausted | repeated-refusal | owner-cancelled | other` |
| `cost` | Priced when the provider's pricing allows — the LC-P3-06 ledger carried `cost = Unknown(UNPRICED)` until priced 2026-11-16; the pilot records price basis and date, or the same unknown, honestly |

## 9. Signing

**Signed by:** `owner / 2026-11-24`. The completed record is signed by the owner (name/date) and referenced by
P4-CAP's real-model step and the pilot ticket before the first request is
sent. A change to any §1–§7 field re-opens the record; a run started under
an older revision is stopped and re-authorised. This mirrors the LC-P3-06
precedent, where the authorisation preceded the run and the record stated
its own limits rather than claiming more than was measured.
