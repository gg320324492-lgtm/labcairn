# The workbench's two missing evidence operations — design note

**Status:** written 2026-11-02; **built 2026-11-02**. It covers the fourth
carried limitation in [`PHASE_2-work-orders.md`](PHASE_2-work-orders.md) §5:
*"the product has no operation that extracts a claim or accepts a model's
proposal."* That phrase bundles two operations with different semantics, so
they are separated below. **The owner decided the eight points in §3 on
2026-11-02**, and §4 records where each decision landed and which witness
reddens when it is broken.

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

## 3. The owner's decisions, taken 2026-11-02

1. **Does extraction ever write a person's claim?** **Decided: no.** Every
   extraction writes a `model_proposal`, even when a person pressed the
   button. The person's act is acceptance, and the two records stay
   distinguishable.
2. **Who is the proposal's `created_by_id`?** **Decided: a stable
   provider+model string**, `"<provider>:<model>"` (for example
   `"anthropic:claude-sonnet-5-5"`), built from the invocation's own fields.
   It is shown nowhere today; if it is shown, its spelling is already a
   contract.
3. **May the person amend the text before accepting?** **Decided: no —
   accept-as-is in this batch.** Amendment is a separate operation with its
   own semantics; `uq_evidence_task_span` makes the same words one claim.
4. **Is acceptance reversible?** **Decided: no undo.** A correction is a new
   record, as a correction to a judgement on the chain is.
5. **What identity does `user_id` carry?** **Decided: a self-reported
   string**, the CLI's trust level. The product keeps no accounts and proves
   no identity, and the surfaces say so.
6. **Which provider, model and budget does extraction use?** **Decided: the
   service's assembly supplies a provider invocation and grants; with no
   provider the act refuses with the layer's reason and writes nothing.**
   Never silently simulated.
7. **What provenance must the acceptance keep?** **Decided: refuse if the
   source changed between extraction and acceptance.** C1's question is then
   about different bytes, and accepting would attest words the proposal was
   not written about.
8. **May an accepted record be cited?** **Decided: yes.** A report cites the
   person's record; the proposal is kept and never promoted.

## 4. What was built, and the witnesses

**The application operations.** `extract_claim`
(`src/labcairn/application/extraction.py`) reads the ledger's stored text at
the address, asks the model through `request_model` for a claim and its
quotation, checks the quotation against the material, and records the answer
through `record_model_proposal` with `created_by_id="<provider>:<model>"`.
`claim_extraction_use` is the one derivation of the approval's arguments, so
the question asked and the request made cannot disagree.
`confirm_proposal` (`src/labcairn/application/evidence.py`) now accepts
as-is: the person's record carries the proposal's text unchanged, a dispute
requires a note and a confirmation refuses one, and acceptance is refused
when the source has drifted.

**The routes.** `POST /claims/extract` (body:
`source_id`, `locator_key`, `user_id`, `provider`, `model`, `destination`,
`subject_ref`, `purpose`, `approval_id`) and
`POST /records/{evidence_id}/accept` (body: `user_id`, `verdict`, `note`).
The accept route calls `confirm_proposal` unchanged, so the CLI's
`task proposal-confirm` and the route produce the same `ProposalSettled`.
The extract route spends the provider invocation and grants the service was
assembled with; with none it refuses with `claim_extraction_no_provider`.

**The witnesses.**

| Property | Witness |
|---|---|
| Extraction writes a proposal, never a person's claim | `tests/test_api.py::test_an_extraction_writes_a_model_proposal_and_never_a_persons_claim` |
| The proposal names the model that answered | the same test (`created_by_id == "fake:scripted"`) |
| Acceptance supersedes the proposal and attests the person's record | `tests/test_api.py::test_accepting_a_proposal_supersedes_it_and_attests_the_persons_record` |
| A dispute without a note is refused and writes nothing | `tests/test_api.py::test_a_dispute_without_a_note_is_refused_and_writes_nothing` |
| A confirmation carrying a note is refused | `tests/test_api.py::test_a_confirmation_that_carries_a_note_is_refused` |
| A source that drifted is refused at acceptance | `tests/test_api.py::test_a_proposal_whose_source_changed_is_refused_at_acceptance` |
| No provider: refusal, nothing written | `tests/test_api.py::test_an_extraction_with_no_provider_is_refused_and_writes_nothing` |
| No approval: refusal, nothing asked or written | `tests/test_api.py::test_an_extraction_with_no_approval_is_refused_before_anything_is_asked` |
| The panel posts both verdicts, re-reads `/records`, shows the person's record | `web/src/views/ProposalsView.test.tsx` — "confirms as-is through the route, then reads the ledger again" and "refuses a dispute with no note before sending…" |
| The CLI's settlement still speaks the same shape | `tests/test_cli.py::test_task_proposal_confirm_settles_a_models_proposal_through_the_console` |

**What is not built.** A CLI command that starts an extraction (the route and
the application operation exist; the console's half is acceptance, as before),
and a production assembly that constructs a provider for `serve` — the
service refuses the act until an operator wires one, which is decision 6's
"absent, never simulated".
