# LC-P2-16 — The workbench for the guidance line — task breakdown

**Status:** planned on 2026-10-31, after the owner's decision that the
workbench is filled in **before** any desktop shell is considered. **This is
a plan, not a claim**: nothing in it is built yet, and the acceptance
clauses in §4 name the tests that do not exist yet either.

**Why this work order exists.** Phase 2's line has landed where it matters
— the model's answer enters the ledger, a person's word settles it, the
guidance rules are distilled from the advisor's own cases, and the three
roles have contracts and prohibitions. **And the workbench has not moved at
all**: `web/package.json` still says *"Phase 1 baseline skeleton, no
product features yet"*, and `git log` over the Phase 2 range shows the only
change under `web/` is a regenerated TypeScript contract. So the phase's
capability is real and **invisible** — a person who opens the application
cannot see the chain the phase built.

**What "invisible" means here, precisely.** The workbench's own rule is in
`web/src/views/EvidenceView.tsx`: *"They do not carry the evidence records
themselves — the contract has no evidence route — so this view does not
draw any … A panel that drew a list of claims it could not see would be a
second spelling of the evidence model, and a reader would believe it."*
**So the order is fixed: the contract first, the view second.** A view
cannot draw what the API does not carry, and the API cannot carry what the
application layer does not read.

---

## 0. How to read this document

§1 says what this work order must produce and what it must not. §2 says
the decisions that shape it. §3 is the work, one subtask at a time, each
with the files it owns. §4 is the acceptance, mapped to where it is
carried. §5 is what this work order cannot deliver, and why. §6 is the
file-ownership map — **the contract that lets more than one agent work on
this at once**. §7 is what "done" means.

## 1. Goals and boundaries

### 1.1 What LC-P2-16 must produce

**A workbench that shows the guidance line's chain, and lets a person act
on it:**

| # | What the workbench shows | What it lets a person do |
|---|---|---|
| 1 | **The advisor's trajectory**: the comments, the edits, the responses, the version graph | read them, in the order the paper was corrected |
| 2 | **The guidance rules**: each rule's state (candidate / confirmed / disputed), its scope, **its counterexamples**, who proposed it and who confirmed it | **confirm or dispute a rule** — a person's act, through a door that exists |
| 3 | **The proposals**: the model's answer and the person's verdict on it, side by side, each saying whose words it is | read which one a report may cite, and why |
| 4 | **The loop, on demand** | ask for a judgement on a comment, through the consent layer's gates |

### 1.2 Already done — removed from scope

- **The layer's readers.** `application/chain.py` reads the comments, the
  edits, the response states and the project graph; `application/guidance.py`
  reads and writes the guidance rules and their confirmations. **These are
  the application layer's own objects**, and the API returns them as they
  are — a route does not re-spell them.
- **The evidence ledger's confirmation door.** `attest_claim` and
  `confirm_proposal` exist, with a CLI command each and a record that says
  whose word stands behind what.
- **The OpenAPI → TypeScript generation.** `python -m labcairn.api.typescript`
  regenerates `web/src/api/generated.ts` from the models, so the contract's
  new shapes reach the front end without a hand-written copy.
- **The web's own discipline** — a view draws only what the contract
  carries — which is why §3 puts the routes before the views.

### 1.3 Explicitly not in scope

- **A desktop shell.** Packaging and multi-platform distribution are
  **Phase 3's row** ("packaging", "Windows/macOS/Linux distribution"), and
  Phase 2's exit gate is a *capability* measurement. The owner's decision
  of 2026-10-31 was to fill the web interface in first; **a shell over a
  skeleton is a harder web page**, and the licence question (the repository
  deliberately has no `LICENSE` file) is a distribution question, not an
  interface one.
- **The paper's own content.** The pilot's corpus is the owner's
  unpublished paper and it lives outside this repository. The workbench
  shows what the ledger holds; **it is not a place for the paper to be
  uploaded**.
- **The reading's agreement number.** That belongs to the pilot's records
  in the material library, and the owner decided it stays out of this
  public repository.

## 2. The decisions that shape it

### 2.1 A view draws only what the contract carries

The evidence view's own docstring is the rule, and this work order keeps
it: **a panel that drew a list it could not see would be a second
spelling of the model, and a reader would believe it.** So every view in
§3 has a route behind it, and the route is the thing that is witnessed.

### 2.2 The routes return the application's own objects

A route is a surface over the application layer, not a second model of it.
The chain's comments are `application.chain`'s `ChainComment`; a rule is
`application.guidance`'s `GuidanceRule`; a record is the ledger's own
`EvidenceRecord`. **The OpenAPI document is generated from those models**,
so the front end's types cannot drift from the layer's — and the
generated TypeScript is regenerated, never hand-edited.

### 2.3 A rule's confirmation is a person's act, and it needs a door

The rules are proposals until a person confirms them, and ADR-0016 D8 says
so: *"a rule distilled from cases is a candidate until a human confirms
it."* The retrieval **does not serve a candidate** unless the caller asks
for it explicitly — *"a proposal reaching a card would be a proposal
dressed as a record."* **So without a door, no rule can ever become
confirmed, and the roles have nothing citable to work from.** The door is
the operation (`write_guidance_rule_confirmation`) plus a CLI command and
an API route; the second-reader rule applies to it exactly as it applies to
the rules themselves.

### 2.4 Asking for a judgement is a gated two-step action

The three roles are a **model** path: it spends a grant, an approval and
a budget, and its answers enter the ledger as proposals. So the workbench
offers **"ask for a judgement on this comment"** as two steps — a request
that writes a question down, and a run that spends the consent — and never
as a button that quietly spends. The gate is the consent layer's, not the
interface's.

### 2.5 The workbench says whose words each thing is

Every panel says who produced what: the model's answer is the model's, the
person's record is the person's, and the report cites the person's. **A
merged view that blurred them would be the "second spelling" this work
order exists to avoid.**

## 3. The work

### T00 — The contract's outlets

The API routes and the shapes they carry: the trajectory (the comments,
the edits, the response states, the project graph), the guidance rules with
their counterexamples and their state, and the task's evidence records.
**No view work in this subtask** — the routes are the deliverable, and
each is witnessed by the API's own test.

### T01 — The rules' confirmation door

The CLI command and the API route by which a person confirms or disputes a
rule, with the second-reader rule enforced and the refusal named. **This
is the door the roles' citations depend on**, and it is owed from the
confirmation-door round of 2026-10-31.

### T02 — The trajectory view

The workbench's panel for the advisor's correction history: what the
advisor wrote, what changed in response, and how the versions stand.

**What the route it draws actually carries, measured by the route's
author.** The versions in the graph are a **frozenset**, so the array the
contract serialises has **no stable order** — the view must not depend on
one, and the contract says so. The route asks for the response states
**once per comment**, so a panel with many comments asks many times. And
there is **no outlet that lists the chain's keys**, so the view can draw
only the trajectory of an issue the caller already names — **a panel that
cannot list what there is to look at is a panel with no way in**, and
whether that needs an outlet is the owner's call, not this plan's.
**Both are written here rather than discovered by the view's author.**

### T03 — The guidance view

The rules with their state, their scope, **their counterexamples**, and
the confirm/dispute action from T01.

### T04 — The proposals view

The model's answer and the person's verdict, side by side, each labelled
with whose words it is, and which one a report may cite.

### T05 — The loop, on demand

The application-layer operation that routes a request to the roles and runs
the ones it names, under the gates — and the workbench's two-step action
that asks for it and then runs it. **This is the piece that makes "the
agents work in the formed style" operable rather than merely true of the
backend**, and it is the largest of the subtasks.

### T06 — The demonstration and the acceptance record

The demonstration that the workbench shows the chain and that a person can
act on it, and this work order's acceptance record.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The test |
|---|---|---|
| A1 | The contract carries the trajectory, the rules and the records | the API's route tests |
| A2 | A rule's confirmation is refused when the confirmer is the proposer | the rules' confirmation test |
| A3 | A view draws nothing the contract does not carry | the view's test, and the route behind it |
| A4 | The counterexamples travel with the rule that cites them | the guidance view's test |
| A5 | The model's answer and the person's verdict are distinguishable in the interface | the proposals view's test |
| A6 | Asking for a judgement asks before it spends | the loop's request-and-run test |
| A7 | The generated TypeScript is what the models produce | the contract-drift test |
| A8 | The demonstration runs and its exit code means something | the demonstration's test |

## 5. What this work order cannot deliver, and why

- **It does not deliver a desktop application.** That is Phase 3's
  packaging row, and the owner decided the interface comes first.
- **It does not make the guidance good.** Whether a rule helps a student is
  LC-P2-14's question; this work order makes the rules *visible and
  contestable*, which is a precondition for that question and not an
  answer to it.
- **It does not put the paper in the application.** The corpus stays
  outside this repository, and the workbench reads the ledger.
- **It does not change the consent layer's gates.** The workbench asks
  through them; it does not get its own.

## 6. The file-ownership map

| Subtask | The files it owns | The shared files it touches |
|---|---|---|
| T00 | `src/labcairn/api/routes.py`, `src/labcairn/api/contracts.py`, `tests/test_api.py` | `web/src/api/generated.ts` (regenerated) |
| T01 | `src/labcairn/cli/commands.py`, `tests/test_cli.py` | `src/labcairn/application/refusal.py` |
| T02 | `web/src/views/TrajectoryView.tsx`, `web/src/views/TrajectoryView.test.tsx` | `web/src/app/Workbench.tsx` |
| T03 | `web/src/views/GuidanceView.tsx`, `web/src/views/GuidanceView.test.tsx` | `web/src/app/Workbench.tsx` |
| T04 | `web/src/views/ProposalsView.tsx`, `web/src/views/ProposalsView.test.tsx` | `web/src/app/Workbench.tsx` |
| T05 | `src/labcairn/application/roles_run.py`, `tests/test_roles_run.py` | `src/labcairn/application/refusal.py`, `src/labcairn/application/__init__.py` |
| T06 | `examples/workbench_demo.py`, `tests/test_workbench_demo.py`, `docs/acceptance/LC-P2-16-acceptance.md` | `.github/ci-shards.json`, `tests/evaluation/manifest.py` |

**And the shared files.** `src/labcairn/application/refusal.py` is shared
with every work order that refuses something, and `web/src/app/
Workbench.tsx` with every view. **Neither may be dispatched at the same
time as another piece that touches it** — which is why T02, T03 and T04
touch the same file and are therefore one piece of work rather than three.

## 7. What "done" means

1. **The workbench shows the chain**: the advisor's trajectory, the rules
   with their counterexamples, and the proposals with the person's verdict.
2. **A person can confirm or dispute a rule from the workbench**, and the
   refusal is named when they cannot.
3. **Asking for a judgement asks before it spends**, and the answer enters
   the ledger as a proposal a person can settle.
4. **Every view's content is the contract's content**, and the generated
   TypeScript is what the models produce.
5. **The acceptance clauses above have a named test each**, and the
   demonstration runs on every suite with its exit code as the assertion.
