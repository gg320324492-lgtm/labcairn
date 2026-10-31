# The confirmation door — acceptance

**Work:** the door a person uses to stand behind a claim, and to settle a
model's proposal · **Date:** 2026-10-31 · **Status:** landed, witnessed,
mutation-checked, and exercised against the pilot's own proposal.

**What this is.** Two application-layer operations and two CLI commands, so
that a person's word can reach the ledger:

| The operation | What it does |
|---|---|
| `attest_claim` | a person stands behind **their own** claim: it becomes `user_attested`, the attestation is logged as a C4 entry carrying that person's id, and the record becomes citable |
| `confirm_proposal` | a person confirms or disputes a **model's proposal**: the proposal's log gains the person's verdict, the person's own record is written at the same address, and the proposal is superseded by it — kept, not deleted |

**What this is not.** It is not a way to make a model's answer true, and it
is not a way for a model to promote itself. A model's proposal still reaches
`planned` and no further, and the model still never becomes the author of
anything.

---

## 1. The decisions, and where each is held

| # | The decision | Held by | Witnessed by |
|---|---|---|---|
| D1 | **A person's own claim can be attested, and the ledger says *which* person.** The attestation is a C4 entry — the check whose only verdict is `not_checked` — so the entry says *no machine checked this, and a person is standing behind it*, and it carries that person's id | `attest_claim`, `evidence/store.py`'s `attest` | `test_a_person_attests_their_own_claim_and_the_ledger_says_who` |
| D2 | **A model proposal is never attested in place.** The record model refuses `user_attested` for a creator that is not a person, and the refusal names the route that *is* open | `attest_claim`'s refusal, ADR-0016 D2 | `test_a_models_proposal_cannot_be_attested_in_place` |
| D3 | **A person's settlement of a model's proposal is the person's own record, and the proposal is superseded by it.** The store's own exit for a record nobody may promote — *"a person writes their own record, and the rule's is kept and marked"* — is what the schema leaves, and it is what the door takes. **The settlement is logged on the person's own record, not on the proposal's**: the old row is marked and the new one carries the attestation, which is also what keeps a product module out of the ledger's verification write (the threat model's C14) | `confirm_proposal`, `evidence/store.py`'s `supersede_record` and `attest` | `test_a_person_settles_a_models_proposal_and_the_proposal_is_kept` |
| D4 | **The proposal's own status and creator do not move.** A model proposal reaches `planned` and no further, and the model's name on it is not rewritten: what a person's word does is stand in front of it, in the person's own name | `confirm_proposal` | the same witness |
| D5 | **A proposal is settled once, the verdict's vocabulary is closed, and nobody signs nothing** | `confirm_proposal`'s three refusals | `test_a_proposal_is_settled_once`, `test_the_verdicts_are_a_closed_vocabulary`, `test_nobody_signs_nothing` |
| D6 | **The console reaches both.** `labcairn task claim-attest` and `labcairn task proposal-confirm` | `src/labcairn/cli/commands.py` | the two CLI witnesses in `tests/test_cli.py` |

## 2. The ADR that had to be corrected

**ADR-0016 D2's promotion diagram was unreachable.** It said a model
proposal reaches `user_attested` when a named human attests it — and D2's
own rule, and the record model's constructor, forbid exactly that. The
diagram and the constructor could not both be true.

**The correction is the store's own answer**, which `evidence/store.py` had
been saying in its docstring all along: the only route to `user_attested`
needs `created_by == 'user'`, so a record nobody may promote *"has nowhere
to go … Superseding is the exit the schema provides: a person writes their
own record, and the rule's is kept and marked."*

So the diagram now reads:

```
a person's own record ──(at the same address)──> user_attested, attributed to that person
        └── supersedes ──> the proposal, which is kept and marked
```

**Nothing was weakened to make this work.** The constructor's rule, the
citability gate, the one-record-per-span rule and the state machine are
exactly as they were; the ADR's *diagram* was the thing that was wrong,
and it now says what the code already did.

## 3. The mutations, and what each one proved

Each mutation was applied to the working tree, run, and reverted; the
witnesses that reddened are named.

| The mutation | What reddened | What it proved |
|---|---|---|
| the person's id not written into the record they wrote | the settlement witness | the record says *which* person wrote it |
| the verdict dropped from the proposal's log entry | the settlement witness | the log says what the person returned |
| the person's record left unattested | the settlement witness | the settlement really attests |
| the "settled once" guard removed | `test_a_proposal_is_settled_once` | a proposal is settled once |
| the verdict's vocabulary opened | `test_the_verdicts_are_a_closed_vocabulary` | the vocabulary is closed |
| the empty-identity guard removed | `test_nobody_signs_nothing` | nobody signs nothing |
| the "not the author" guard removed | `test_a_models_proposal_cannot_be_attested_in_place` | a proposal is not attested in place |

## 3.1 What building the door found in the tree

**The threat model's C14 caught the first version of this door.** C14 is
*"no product operation runs the ledger's checks"* — the product writes
claims and never verifies them. The first version wrote the person's
verdict onto the proposal's log, which meant calling the ledger's
verification write from a product module: a second spelling of the
settlement, and a product operation behind the write the threat model
forbids. **The store's own design was the answer** — the old row is
marked and the new one carries the attestation — so the door was
rewritten to take it, and **nothing in the threat model or its witness
had to be touched**.

**And the branch carried a latent defect that the CI's shard order hid.**
The exchange event's payload schema was registered as a side effect of
importing the model path's own module, so a process that only *read*
events had no schema for it and a stored exchange's payload was accepted
unchecked — the defect `runtime/event.py`'s docstring names (*"a schema
registered as a side effect of importing a writer is therefore absent in a
process that only reads"*"). The registration now sits in the runtime
package's own import, beside the trajectory's, and
`tests/test_event_payload_vocabulary.py` asks about it in a fresh
interpreter the way it asks about the recovery layer's. **The full suite
on one machine is what surfaced it**: the test passed alone and failed in
the suite, because the registry is populated by import order.

## 4. What was measured, and on what tree

- `tests/test_application_evidence.py` — 20 passed (14 before this work, 6
  new).
- `tests/test_cli.py` — the two new CLI witnesses passed.
- `mypy --strict` over `src` and `tests` — clean. `ruff check` and
  `ruff format --check` — clean.

## 5. What this work does not carry

- **It does not make a model's answer true.** A proposal stays a proposal;
  what changes is that a person may stand in front of it, in their own
  name, and then the report cites *their* record.
- **It does not say the person's word is right.** `user_attested` means "a
  named person said so", and the record says who. Nothing here checks the
  person's judgement.
- **It does not give the console a command that writes a model's proposal.**
  The model path is code; the operator's half is this command. That gap is
  named in the pilot's task book.
- **It does not settle the difference between "confirmed" and "disputed" as
  a state.** The evidence vocabulary has no state for it — the guidance
  rules' `confirmed` / `disputed` states do — so on this path the
  distinction lives in the person's words and in the proposal's log entry.
