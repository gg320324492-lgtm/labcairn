# LC-P2-01 — The zero-send negative test plan

**Status:** drafted 2026-10-30 with the work order, **before** the
implementation. **What it is for:** P2-AMD-01's second step asks for a
demonstration in which an unapproved request for an unpublished fragment
**sends nothing**, the operation approval stays unspent, and the reason is
a machine-readable one. **This plan says which cases that demonstration
must cover and what each one asserts.**

**The rule the plan is built on:** *a refusal that is claimed must be
provable.* "The network call count is zero" is a claim about the world, so
**the count has to come from something that would notice a call**, and not
from the code's own say-so.

## 1. How the count is taken

**Two independent counts, and both must be zero.**

**The provider's own count.** `FakeProvider` records every call it is
asked to make. **A request that never reaches the provider is not in the
count** — and that is the point: the count is taken at the boundary the
call would have crossed, not at the decision that stopped it.

**And the process's own count.** The demonstration's outbound path is the
only thing in the process that opens a socket, so the test **asserts that
the path was never entered** — by holding the provider's transport at the
adapter's edge and showing it was never touched. A count taken from inside
the decision is a count of the decision.

**And the approval's state.** The operation approval is read from the
**store**, not from the layer that would have spent it. A refusal that
left the approval looking unspent in memory but spent in the row would
pass a memory-reading test and fail the product.

## 2. The cases

**Each case is a negative: the request must be refused, and the refusal
must say why in a way a caller can branch on.** The "no" column is the
reason's machine-readable value; the "sent" column is the provider's call
count; the "spent" column is the approval's state in the store.

| # | The situation | The refusal | sent | spent |
|---|---|---|---|---|
| 1 | **No operation approval at all** | `approval_missing` | 0 | — (there was none) |
| 2 | An operation approval, and **no material-purpose grant** | `consent_no_grant` | **0** | **no** |
| 3 | A grant for the material, and a **different destination** | `consent_destination_not_granted` | **0** | **no** |
| 4 | A grant that is `train_reuse` where the request is `external_transmit` | `consent_no_grant` | **0** | **no** |
| 5 | A grant **withdrawn** before the request | `consent_grant_withdrawn` | **0** | **no** |
| 6 | A grant whose window has **closed** | `consent_grant_expired` | **0** | **no** |
| 7 | A grant for a **different project** | `consent_no_grant` | **0** | **no** |
| 8 | A granted approval, and the **budget's price is unknown** | `budget_unknown_price` | **0** | **no** |
| 9 | A granted approval, and the **budget is spent** | `budget_exhausted` | **0** | **no** |
| 10 | A granted approval, and the provider has **never been probed** | `capability_unverified` | **0** | **no** |
| 11 | A request for a **schema the provider cannot produce** | `output_not_decodable` | **1** | **yes** |
| 12 | A request that was **sent and did not answer** | — (it is `unknown`, not a refusal) | 1 | **yes** |
| 13 | A request **retried after a restart** | — (the retry is blocked) | **1** | **yes** (once) |

**Cases 2 through 10 are the ones the demonstration is about**, and they
share a shape: **the request is refused and nothing crossed the boundary.**
Case 11 is the first one that *does* send, and it is in the plan because a
plan that only covers refusals would not say what happens after one.

**Case 13 is the one that keeps the plan honest.** A retry across a
restart must not pay twice: the provider's count is **1**, not 2, and the
approval was spent **once**. **This is LC-P2-02's durability, exercised
here** because it is the first place a paid call is at stake.

## 3. What each case asserts beyond the count

**A refusal with a reason is not enough.** Each case also asserts:

- **the reason is in the layer's vocabulary**, and the mapping is closed in
  both directions (the same witness LC-P2-01's A13 names);
- **the approval's state in the store is unchanged** — read from the row,
  not from the layer;
- **nothing was recorded as a request**: the event log has no `requested`
  entry for a case whose count is zero. **A log entry saying "prepared"
  and nothing else is correct; a log entry saying "requested" is a lie.**
- **and the refusal is a refusal, not a crash**: the path returns the
  refusal with its reason, and the exit code is the refusal's.

## 4. The demonstration

**`examples/model_request_demo.py` runs the cases above with
`FakeProvider` and sends nothing.** Its output says, for each case, the
refusal's reason and the two counts — and the counts are the point, so
they are printed rather than only asserted.

**And the demonstration is run by a test**, because a demonstration nobody
runs is one that quietly stops working.

**What the demonstration does not do:** it does not call a real provider,
it does not use a real key, and it does not require the network. **A real
cloud smoke is a separate, authorised exercise** — it needs the owner's
authorisation, a limit, and synthetic content that may be sent, and it is
not part of this plan.

## 5. How the plan is proved

**Each case is a witness, and each case's witness must fail when its
property breaks.** The mutations this plan expects:

| The mutation | The case that must go red |
|---|---|
| the material check is moved **after** the approval is consumed | case 2, and the spent column |
| the provider is called **before** the gate asks | cases 2–7, the sent column |
| the budget's unknown price is treated as zero | case 8 |
| the probe's absence is treated as a pass | case 10 |
| the retry does not check the approval's state | case 13, the sent column |
| the refusal's reason is a string rather than the layer's member | every case's reason assertion |

**And the tree is restored after each one.** A mutation that was never
applied is reported by anyone who does not check as a survivor, and that
false negative looks exactly like a success.
