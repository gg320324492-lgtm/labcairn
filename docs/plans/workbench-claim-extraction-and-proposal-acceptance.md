# The workbench's two missing evidence operations — design note

**Status:** written 2026-11-02. **Design only — nothing here is implemented.**
It covers the fourth carried limitation in
[`PHASE_2-work-orders.md`](PHASE_2-work-orders.md) §5: *"the product has no
operation that extracts a claim or accepts a model's proposal."* That phrase
bundles two operations with different semantics, so they are separated below,
and the points that need the owner's decision are listed rather than decided
here.

---

## 1. What exists today, measured in the tree

| Piece | Where it is | What it does | What it does not do |
|---|---|---|---|
| `POST /claims` | `src/labcairn/api/routes.py` (`post_claim`) | records a **person's** claim at a source address; writes the anchor and an `extracted` record through `record_claim` | it takes the text from the caller — nothing reads the source to *find* a claim |
| `task claim` | `src/labcairn/cli/commands.py` (`task_claim`) | the CLI's spelling of the same operation, same layer call | same gap |
| `record_model_proposal` | `src/labcairn/application/evidence.py` | writes a model's answer as `created_by=model_proposal`, status `planned`, bound to the locator it names | **it has no route and no CLI command.** Its callers are tests and the model-request path; a person cannot start it from a surface |
| `confirm_proposal` | `src/labcairn/application/evidence.py` | writes the person's own record at the same address, supersedes the proposal (`superseded_by`), and attests the person's record with their verdict and note; the proposal is kept and never promoted | **it has no route.** Only `task proposal-confirm` (CLI) calls it |
| `GET /records` | `src/labcairn/api/routes.py` | returns the ledger's records with `created_by`, `superseded_by` and the verification log | — |
| Proposals panel | `web/src/views/ProposalsView.tsx` | draws proposals beside the person's verdict and says which a report may cite | **it offers no act**; its docstring names this gap and the missing route |

The rules that already hold and that these operations must keep:

- **A model's proposal never becomes a person's word.** `confirm_proposal`
  writes a *new* person record and marks the proposal; ADR-0016 D2 is
  enforced by the record constructor, not by the caller.
- **An attestation nobody signs is not an attestation.** `user_id` is an
  argument and an empty one is `attestation_identity_empty`.
- **A claim is bound to a locator and to the source bytes it was read
  against.** `record_claim` and `record_model_proposal` both bind the anchor
  to the source's *current* hash; a changed source makes C1 fail later
  rather than silently re-pointing the claim.
- **A report cites a person's record, not a model's proposal.** The panel
  says so; the report builder refuses the alternative.

## 2. Proposed shapes (non-binding)

### 2.1 Extract a claim

`POST /sources/{source_id}/claims/extract` with a body naming the address and
(optionally) an instruction. The route calls a **new application operation**
`extract_claim` that:

1. reads the address through the same material path `record_claim` uses;
2. asks the configured provider for a structured answer — a `ClaimRequest`-shaped
   statement plus the span it copied — under the existing `model.request`
   approval, with provider and model id recorded;
3. writes the answer through **`record_model_proposal`**, never
   `record_claim`. Extraction is what a model says; it is a proposal by
   definition.

Offline or provider-less, the operation **refuses** (`not_implemented` /
`provider_unavailable`) rather than returning an empty extraction. The
workbench's Sources panel would offer the act on an address it already draws;
the Proposals panel would then draw the result, which it already knows how to
draw.

### 2.2 Accept a proposal

`POST /records/{evidence_id}/accept` with `{user_id, verdict, note}`. The
route calls **`confirm_proposal` unchanged** — the application operation the
CLI already uses — so the two surfaces cannot drift. `verdict` is the closed
vocabulary `confirmed | disputed`; `note` is required for a dispute and
refused for a confirmation (the CLI's rule). The guards apply as on every
other change: own origin, session token, and the layer's refusals rendered
unchanged.

The Proposals panel gains two buttons and a field for the person's id; the
write goes through the route and the panel re-reads `/records`, exactly as
the Approval panel re-reads `/task` after a grant.

## 3. What the owner has to decide

1. **Does extraction ever write a person's claim?** Recommended: no —
   always a proposal, even when a person pressed the button. The person's
   act is acceptance, and the two records stay distinguishable.
2. **Who is the proposal's `created_by_id`?** A stable provider+model string
   (`anthropic:claude-…`)? The record's `created_by_id` is shown nowhere
   today; if it is to be shown, its spelling becomes a contract.
3. **May the person amend the text before accepting?** The current
   `confirm_proposal` writes the person's record at the same span; an amend
   would need a different operation (and `uq_evidence_task_span` makes the
   same words one claim). Recommended: accept-as-is in this batch;
   amendment is a separate operation with its own semantics.
4. **Is acceptance reversible?** The schema settles a proposal once. An
   undo would have to say what happens to the person's record, the
   attestation and the `superseded_by` link. Recommended: no undo; a
   correction is a new record, as the chain's judgements are.
5. **What identity does `user_id` carry, and may it be typed?** There are no
   accounts in the product; the CLI takes a string. If the workbench takes a
   typed name, is that the same trust level as the CLI's? (It is: both are
   self-asserted. The owner should confirm the product says so.)
6. **Which provider, model and budget does extraction use, and is it on by
   default?** The Phase 1 route is "a cloud model behind three roles"; an
   extraction call spends money and needs a `model.request` approval. What
   happens on a fresh workspace with no provider? Recommended: the act is
   absent (or refuses with the layer's reason), never silently simulated.
7. **What provenance must the acceptance keep?** The proposal already
   carries the source hash and span hash. If the source changed between
   extraction and acceptance, does acceptance proceed (the person read the
   text) or refuse (C1's question is now about different bytes)?
8. **May an accepted record be cited, and does the panel say which record a
   report cites after settlement?** Existing rule says a report cites the
   person's record; the owner should confirm that acceptance is enough or
   whether a report-level check must also run.

## 4. Witnesses this design would require (none exist yet)

- A model-free test that `extract_claim` writes `created_by=model_proposal`
  and never `user`; a mutation that swaps the call to `record_claim` must
  fail it.
- A test that `POST /records/{id}/accept` and `task proposal-confirm`
  produce the same `ProposalSettled` shape from the same store.
- A guard test for the accept route (foreign origin, missing token) and for
  the extract route (the same, plus a missing provider).
- A web test that the Proposals panel's accept button posts, re-reads
  `/records`, and draws the person's record beside the marked proposal —
  with the refusal path visible, as the grant button's is.
- A test that extraction on a workspace with no provider refuses with a
  reason and writes nothing.
