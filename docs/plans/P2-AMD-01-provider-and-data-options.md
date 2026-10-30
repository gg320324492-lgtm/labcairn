# P2-AMD-01 — The suppliers and the data categories: what is measured, and what is not

**Status:** drafted 2026-10-30, **as decision support** for the first of the
owner's four decisions in the adjustment's §10.5 — *"which suppliers and
which data categories are permitted"*. **It decides nothing.** It says what
has been measured, what has not, and what each choice would mean.

**The one thing to know before choosing:** **a supplier's name is not a
capability.** The route is a **configuration** (`协议:模型`, e.g.
`anthropic:claude-opus-5`), and whether a supplier may serve a request is
decided by **the capability probe's record**, not by its name or by a
published parameter count. P2-AMD-01 says this twice — *"不要写死任何模型
ID、端点、价格或能力；所有供应商均需独立连通性与结构化输出实测"* — and
the tree already has the mechanism.

## 1. What has actually been measured

**One supplier, one model, one protocol, one date.**

| | |
|---|---|
| The supplier and model | **`MiniMax-M3.1-Flash`** |
| The protocol | `anthropic` (the `pydantic-ai` one) |
| The date | **2026-10-28** |
| The record | ADR-0016's Context, and `tests/test_real_provider_smoke.py` |

**And the four probed capabilities** (`src/labcairn/providers/capabilities.py`):

| Capability | The measured answer |
|---|---|
| `tool_calls` | **works** |
| `usage_reporting` | **works** |
| `structured_output_native` | **declined** — the client refuses it **before the request is sent** |
| `structured_output_prompted` | **declined** — the same |

**And what the second row means in practice.** The probe found that
**neither structured-output form is available on this supplier at all** —
and the refusal happens inside the client, so the request never leaves the
machine. **A design that assumes "the model returns JSON" starts from a
refusal**, which is ADR-0016's Context in one sentence, and it is why the
schema has to be enforced **on the way in and on the way out** (ADR-0016
D3).

**What has not been measured: any other supplier.** No probe record exists
for anything else, and **a provider with no probe record is blocked** from
a request that needs a schema — the adapter refuses with *"no capability
probe has run for this provider"*.

## 2. The protocols the tree speaks, and what that means for a choice

**Two protocols**, both through `pydantic-ai`: **`anthropic`** and
**`openai`** (`src/labcairn/providers/pydantic_models.py:137-150`).

**And that is the practical route to the suppliers the adjustment names.**
A supplier that offers an **OpenAI-compatible endpoint** can be configured
under the `openai:` protocol without a line of new code — **and without a
line of new code it also has no measurement**, so it is blocked until it is
probed.

**So the honest statement about the three suppliers the adjustment names is
this: only one of them has been probed, and the other two are reachable
only if they speak one of the two protocols the tree already speaks — which
is a thing to establish by probing, not by assuming.**

## 3. What a probe has to answer, per supplier

**The four capabilities, and what each one costs the design if it is
missing:**

| Capability | If it is missing |
|---|---|
| `tool_calls` | The role cannot call a tool; the trajectory agent's job is partly reading, so this is the capability that matters most for role A. |
| `usage_reporting` | **The cost cannot be measured**, and a budget whose consumption cannot be measured **fails closed** (ADR-0018 D7). **This one is not optional for a paid route.** |
| `structured_output_native` | The schema must be enforced **on the way out**: the output is validated against the schema, and a decode failure is a **refusal with a reason** (LC-P2-01 A10), not an empty result. |
| `structured_output_prompted` | The same, by a longer road. **If neither form is available, the supplier cannot serve a role with a schema at all** (ADR-0018 D5), and the roles are exactly schemas. |

**And two questions a probe does not answer, that the owner's decision
must:**

1. **What may this supplier receive?** The material-purpose grant says
   *this material may go to this place* — and "this place" is a
   **supplier**, so the grant and the route have to name the same thing.
   **A supplier that is permitted for one purpose is not permitted for
   another.**
2. **What does it cost, and is that cost observable?** An unknown price
   fails the budget closed, so a supplier with no published, stable price
   **cannot be on a paid route** until its price is recorded.

## 4. The data categories, and the three tiers

**The adjustment's rule is a default, and the default is the safe one:**
unpublished manuscripts and confidential review files **do not go out**
unless the right holder has reviewed them.

| Tier | What is in it | What it takes |
|---|---|---|
| **May go out** | **Synthetic material** — the fixture corpus, the public corpus, the generated DOCX files | nothing beyond the operation approval and the material-purpose grant |
| **May go out, with a recorded authorisation** | Material whose right holder has agreed to this supplier, this purpose, this class of fragment | a **named grant**, and the grant's scope is the supplier and the purpose, not "the project" |
| **Does not go out** | Unpublished manuscripts, confidential reviews, anything under NDA, and anything whose authorisation is not recorded | — |

**And the boundary is enforced by the grant, not by the configuration.** A
supplier being in `providers.json` says *which supplier the route uses*; it
says nothing about *what may be sent to it*. **Those are two different
permissions** (ADR-0015 D2/D3), and the second one is the one that is
enforced.

## 5. What the recommendation is, and what is not

**A recommendation, not a decision:** permit **one supplier** to begin
with — **the one that has been probed**, so that the first real route has a
capability record and the first budget can be measured — and treat the
others as **candidates awaiting a probe**. **Two suppliers on one role is
not a product capability** (P2-AMD-01 §3), and a second supplier on the
same role without a probe record buys nothing but a second thing to
measure.

**What is not recommended and not decided:** which supplier that is, what
data classes the pilot may use, what the budget is, and whether the pilot
runs at all. **Those are the owner's, and the four decisions in §10.5 are
where they are written down.**

**And one thing that is true regardless of the choice:** **the repository's
own configuration carries a fake provider and nothing else**, so a fresh
checkout cannot spend money by accident — and the route's supplier comes
from the operator's configuration, never from the tree.

## 6. What to do when the decision is made

1. **Probe the chosen supplier(s)** — `labcairn providers probe` — and
   **record the four answers and the date**. A probe record is a
   measurement, and a measurement without a date is a rumour.
2. **Write the grant's scope** — the supplier and the purpose — **before**
   the first real call, not after.
3. **Set the budget's ceiling** — per task and in total — and record the
   price the budget measures against.
4. **If the answer is a supplier that has never been probed**, the first
   thing to establish is **which of the two protocols it speaks**, because
   that decides whether it is reachable at all without new code.
