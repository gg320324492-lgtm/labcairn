# LC-P4-PILOT — what the analysis pipeline would need to carry verification

**Ticket:** the option-B half of
`docs/acceptance/LC-P4-PILOT-verified-by-rule-unreachable-2026-11-28.md` —
*"record the decision that verification lives only inside the analysis
pipeline"*, and the cost of each of its two sub-shapes.
**Date:** 2026-11-28.
**Tree:** `7bcfe53952e969ee1736af3623a656927d550d62` (`main`'s tip as this
window started; the worktree branch `claude/stoic-swirles-ae2142` carries it
unchanged). The record above was measured at `58486d21` and closed at
`f39b96b3` + `339f2042`; both readings are named where they are used.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13 (the project's own
`.venv` at `E:/LabCairn/.venv`).
**Status:** local evidence only. No push, no pull request, no CI run, no merge.
**The measuring window changed nothing under `src/`.** It measured and
recorded.
**Material:** **none of the pilot's was read.** The measurement is a read of
this repository's own source, plus greps over `tests/`, `web/src/` and
`migrations/`. No document text, digest of a document, or key of the pilot
appears in this record. No model request was made.

**This record does not choose.** The record above says the measurement is
neutral about which option the owner should want, and this one is neutral
about both sub-shapes of option B, and about whether option B is worth
choosing at all. It says what each costs.

## What was asked, and what this answers

The record above left one thing unmeasured, and said so plainly in its *What
was not measured* section:

> **The analysis pipeline.** `labcairn.analysis` registers operators and
> renders charts, and its manifests bind a run's inputs and outputs — but it
> appends nothing to any evidence record's log. The option the owner may
> weigh — "verification happens only inside the analysis pipeline" — presumes
> a coupling this tree does not yet have; **the measurement here is that the
> coupling does not exist, not that the pipeline could not carry it.**

That last clause is the gap this record closes. It answers three questions
with the tree's own lines:

1. **What the pipeline does**, and where a verification step would have to
   attach if it carried one.
2. **What the coupling would cost** — the files, the operations, the
   witnesses and the contract that would move — and which of them are
   *already* there because a window wired the verify door.
3. **What each of option B's two sub-shapes costs**, so the owner can weigh
   them against the record's other options.

**And it reports one finding that contradicts the brief**, because the
measurement wins over the brief: **a red witness was found in the tree**, one
that option A's closing left behind and that option A's own record does not
mention. It is named in *A witness that is red on this commit* below, and it
is **not** repaired here — this window does not own `tests/test_threat_model.py`
or `docs/THREAT-MODEL.md`, and the repair is a decision about what the threat
model now says, not a measurement.

---

## 1. The pipeline as it is

### 1.1 What a run does, in the order it does it

`labcairn.analysis.service.run_analysis` (`src/labcairn/analysis/service.py:452`)
is the run path, and its own docstring names seven steps
(`src/labcairn/analysis/service.py:471-483`):

> 1. **admit the path** into the named source root, so that a path naming no
>    source root is refused before anything else happens;
> 2. **build the selection** from the capability's parameters, validated
>    against the operator's own argument model;
> 3. **resolve the source** — the ledger's row for the selection's binding,
>    the file's bytes, and the source's readability.
> 4. **evaluate the operator** from the catalogue, by its id;
> 5. **prepare the environment**, then **write the manifest**, which hashes
>    the *result* and not the figure;
> 6. **render**, if the operator produced a figure, and write it;
> 7. **record the receipts**.

The code says the same thing (`src/labcairn/analysis/service.py:497-581`): the path
(`_canonical_path`, 502), the operator and the selection (505-508), the
source (511), the policy and the bounds (514-516), **the consent**
(`_consume_approval`, 519-531), the evaluation (`_evaluate`, 534), the
manifest (`_build_manifest`, 539-545), the figure (556-563), and the receipts
(`store.unit(workspace.task_id)`, 570-572).

**What the run produces** is `AnalysisRun` (`src/labcairn/analysis/service.py:299-314`): the
`Source`, the `Selection`, the operator's own result object, the
`ReproducibilityManifest`, the `manifest_receipt` and the `figure_receipt`.
**There is no evidence record in it, and no log entry** — by construction,
not by omission.

### 1.2 What the manifest binds

`ReproducibilityManifest` (`src/labcairn/analysis/manifest.py:232-269`) holds
six things, and its docstring says what each is for:

| Field | What it binds |
| --- | --- |
| `input_file: FileRef` | the file the derivation read, and the hash of the bytes it read |
| `operator: NonEmptyText` | the operator that ran, in the one spelling — `labcairn.analysis.mean@1.0.0` |
| `locator: ComputationLocator` | the selection, the operator's version, the parameters |
| `recipe: FileRef` | the recipe the derivation followed, by path and hash |
| `output: JsonValue` | the operator's output, as JSON |
| `output_sha256: ContentHash` | the digest of `output`'s canonical JSON |
| `environment: RenderEnvironment` | where the derivation ran |

**The manifest's own statement of why it exists** is the sentence that
decides this measurement (`src/labcairn/analysis/manifest.py:1-9`):

> LC-P1-10 computes numbers, and a computed number is a different kind of
> claim from a read one. A number read out of a cell is a statement about
> that cell, and the ledger checks it -- C3 re-reads the cell and compares.
> **A number computed from many cells is a statement about a *derivation*,
> and what makes it checkable is not a check but this document.**

**That is the load-bearing sentence.** The tree already says, in its own
words, that a derived number is checked by *re-derivation from the
manifest*, not by C1/C2/C3. Option B's premise — that the pipeline is where
verification lives — is therefore **half-true and half-false in the tree's own
terms**: the pipeline does produce the thing that makes a derived number
checkable (the manifest), and it does **not** produce the thing that moves an
evidence record's status (a `VerificationRecord` in a log).

### 1.3 Where the pipeline writes, and what it can write

The run's only database write is the receipt
(`src/labcairn/analysis/service.py:570-572`):

```python
with store.unit(workspace.task_id) as work:
    for receipt in receipts:
        work.put_artifact(receipt)
```

`UnitOfWork` (`src/labcairn/db/repository.py:152-229`) offers exactly seven
write helpers: `emit`, `put_run`, `put_stage`, `put_operation`, `put_approval`,
`put_checkpoint`, `put_artifact`. **There is no `put_evidence_record`,
no `put_verification`, no `put_anchor`.** The pipeline can write an artifact
receipt and nothing else.

`put_artifact` writes the `artifacts` table (`src/labcairn/db/repository.py:222-228`), whose
columns are fixed by migration `0001_initial_task_store.py:174-215`:
`artifact_id`, `task_id`, `run_id`, `kind`, `relative_path`,
`content_sha256`, `size_bytes`, `revision`, `produced_by`, `producer_id`,
`derived_from`, `staleness`, `staleness_reason`, `media_type`, `created_at`,
`schema_version`. **No evidence-record column, no verification-log column.**

### 1.4 The pipeline has no way to reach the evidence ledger at all

This is the question the brief asks to be shown, and it is shown four ways.

**First, there is no import.** Every import in the analysis package:

```
$ git grep -n "^from labcairn\.\(evidence\|db\|reports\)" -- src/labcairn/analysis/
src/labcairn/analysis/manifest.py:60:from labcairn.reports.receipt import (
src/labcairn/analysis/service.py:94:from labcairn.db.materials import current_texts
src/labcairn/analysis/service.py:95:from labcairn.db.models import SourceRow, SourceTextRow
src/labcairn/analysis/service.py:96:from labcairn.db.repository import TaskStore
src/labcairn/analysis/service.py:97:from labcairn.reports.receipt import ArtifactReceipt
```

**Five import statements, none of them from `labcairn.evidence`.** The two mentions of
`labcairn.evidence.catalog` under `analysis/` are prose in two docstrings
(`src/labcairn/analysis/catalog.py:5`, `src/labcairn/analysis/operators/__init__.py:8`) that cite the *reason* the
analysis catalogue is built from the operators' own constants.

**Second, the words.** Every occurrence of "evidence" under
`src/labcairn/analysis/` is prose — docstrings that say "the evidence
standard this ledger enforces" (`src/labcairn/analysis/units.py:9`), "the only evidence that can
check it" (`src/labcairn/analysis/operators/descriptive.py:31`), and the two docstring citations above. Not
one is code.

**Third, the identifiers.** `git grep -n "evidence_id\|EvidenceRecord\|record_id"
-- src/labcairn/analysis/` returns **nothing**. And
`git grep -n "EvidenceKind" -- src/labcairn/analysis/` returns **nothing**:
the analysis package never produces an evidence record of any kind.

**Fourth, the reverse direction.** `git grep -rn "labcairn.analysis" -- src/`
(excluding the analysis package itself) shows who *does* depend on the
pipeline: `application/analysis.py`, `application/chain.py`,
`application/refusal.py`, `application/reports.py`, `cli/commands.py`,
`reports/__init__.py`, `reports/build.py`, and `reports/manifest.py`. **The
evidence package does not import the analysis package at all** — the coupling
is one-directional and it points *away* from the ledger.

### 1.5 The one link that exists, and what it is

The manifest's `derived_from` is a tuple of `DerivationRef`
(`src/labcairn/reports/receipt.py:18-22`), and the closed union of target
kinds (`src/labcairn/reports/receipt.py:105-118`) **does** include `EVIDENCE_RECORD = "evidence_record"`.

**But nothing writes it.** `git grep -n "EVIDENCE_RECORD" -- src/` returns
three hits, and all three are the *definition* or its documentation:
`src/labcairn/reports/receipt.py:27` (the module docstring), `src/labcairn/reports/receipt.py:109` (the enum member),
and `src/labcairn/reports/receipt.py:109`'s comment. **No module constructs a
`DerivationRef(target_kind=EVIDENCE_RECORD, ...)`.**

What the manifest's receipt *does* write is one `DerivationRef` to the
material file (`src/labcairn/analysis/manifest.py:603-609`):

```python
derived_from=(
    DerivationRef(
        target_kind=DerivationTargetKind.MATERIAL_FILE,
        target_id=manifest.input_file.relative_path,
        content_sha256=manifest.input_file.content_sha256,
    ),
),
```

**So the shape is there and the link is not.** The machinery that would let a
figure say "this came from that claim" exists in the model and is used by no
one. That is a fact about the tree, and it is the nearest thing to a
pre-existing hook for option B that the measurement found.

### 1.6 The consent a verification step would sit inside

A run's consent is a granted `analysis.run` approval, bound to the
capability, the resource key and the **arguments digest**
(`src/labcairn/analysis/service.py:12-22`; `src/labcairn/security/capabilities.py:279-299` — `path`,
`operator_id`, `recipe`, `parameters`). The digest is recomputed at the
moment of use (`_consume_approval`, `src/labcairn/analysis/service.py:866-896`).

**The consent has no evidence record in it.** `AnalysisRunArgs`
(`src/labcairn/security/capabilities.py:279-299`) has four fields and none of them is an
`evidence_id`. The run path never learns which record, if any, the run is
about: `AnalysisRequest` (`src/labcairn/analysis/service.py:278-296`) carries `approval_id`,
`root_id` and `arguments`, and `FigureRequest`
(`application/analysis.py:87-104`) carries `root_id`, `path`, `operator_id`,
`recipe`, `parameters` and `approval_id`.

**This matters for the cost.** A verification step inside the pipeline would
have to be *consented to* — a rule's pass moving a claim's status is a write
to the evidence ledger, and the pipeline's consent is for an analysis. Two
routes exist, and the tree has opinions about both:

* **The approval's arguments would have to carry the record id** — a change
  to `AnalysisRunArgs`'s closed model, a change to the digest, a change to
  what a person is shown when they consent, and a change to every caller that
  builds the arguments.
* **Or the verification would happen under a different consent** — a second
  capability, a second approval, a second digest. `CapabilityId` is a closed
  registry (`security/capabilities.py:73-83`) and an unknown id is a denial
  (`src/labcairn/security/capabilities.py:15-17`), so a new capability is a registry change, a
  policy change and a witness change.

Neither is free, and the tree does not currently offer either.

### 1.7 The check the pipeline's result could face

If a pipeline result were to be verified by one of the ledger's own rules,
which rule could it face? Measured against the three implementations:

* **C1** (`evidence/checks/c1.py`) — resolves every `anchor_id` against the
  ingested material and re-verifies the recorded content hash. A pipeline
  result cites no anchor; the manifest cites a *file*.
* **C2** (`evidence/checks/c2.py`) — matches `record.extracted_span` against
  the text at each anchor's located span, under a declared normalization
  profile. A derived number has no extracted span.
* **C3** (`evidence/checks/c3.py`) — re-reads the anchored cell and compares
  to `record.value` under a declared unit and tolerance. C3's own first
  refusal (`src/labcairn/evidence/checks/c3.py:102-110`) is for a record whose kind is not `NUMERIC`;
  and its refusal for a record with no anchors
  (`src/labcairn/evidence/checks/c3.py:122-127`) is `indeterminate`, which is *not* a pass.

**And C3 cannot be pointed at a derived number at all**, for a reason the
tree states in three places:

* `LocatorKind.COMPUTATION` is a real locator kind (`sources/locators.py:101`),
  and a `ComputationLocator` is its typed shape (`locators.py:293`).
* But `render_locator_key` **refuses** it
  (`material/addressing.py:172-179`): *"COMPUTATION addresses a derived number
  by the operator that produced it and has nothing to extract, so no row of
  `source_texts` should carry it."*
* And the `source_texts` table's own CHECK excludes it
  (`db/models.py:925-930`): *"COMPUTATION is a real LocatorKind but has no
  extracted text — a derived number is addressed by the operator that produced
  it, so it belongs in no row of this table."*

**A derived number therefore cannot be anchored, and a check that needs an
anchor cannot read it.** This is the deepest of the four facts, and it is the
one that decides what option B can mean:

> **The pipeline's output is not a thing the ledger's checks can be run
> against.** A rule's pass, in this tree, is a verdict about *a located
> passage or a located number in a source file*. A derived number is located
> by an operator and a manifest, and it is checkable by re-deriving it — which
> is what the manifest is for.

So a verification step inside the pipeline would not be "run C1/C2/C3 on the
result". It would be one of two other things, and they cost differently:

* **a re-derivation check** — re-run the operator over the manifest's inputs
  and compare the output hash. That is a *new* rule with a *new* checker id,
  and it would have to be added to `labcairn.evidence.catalog`, which is
  built from the check modules' own id constants
  (`evidence/catalog.py:10-18`, "code, not a table"); or
* **an attestation of the manifest** — the pipeline asserting that its own
  output is what the manifest says it is. That is not a rule's pass at all; it
  is the pipeline asserting a fact about itself, which is the thing the
  evidence ledger's structure exists to prevent (`evidence/__init__.py:14-19`:
  *"Verification is not a label ... the status alone never carries the claim"*).

### 1.8 Where a verification step would have to attach

Given 1.4 through 1.7, a verification step in the pipeline would attach at
**one of three points**, and the tree says which of them are open:

| Attachment point | Where | What the tree says about it |
| --- | --- | --- |
| **A. The run's own transaction** | `src/labcairn/analysis/service.py:570-572`, `with store.unit(...)` | The unit's `put_*` helpers have no evidence-record write, and `artifacts` has no column for one. **Would need a new write helper, a new table or column, and the ledger's own contract applied to a write the ledger does not own.** |
| **B. After the run, in the application layer** | `application/analysis.py:177` (`run_figure`) is the seam surfaces call | The application layer *is* where the evidence operations live (`application/evidence.py`), and it already has the collaborators a verify needs — the store, the task, the ledger. **This is the cheapest attach, and it is not "inside the pipeline": it is beside it, in the layer that already owns the ledger.** |
| **C. In the operator's own evaluation** | `_evaluate` (`src/labcairn/analysis/service.py:534`, definition at 979) | The operator computes over cells; it holds no evidence record, no anchor and no log. **An operator cannot verify, because it is given cells and returns a number — it never sees a record.** |

**Attachment point B is the one the tree already supports**, and it is worth
saying plainly what that means for option B's premise: *the seam that could
carry a pipeline-driven verification already exists*, and it is the
application layer — where option A's `verify_claim` already sits.

---

## 2. The coupling's cost

### 2.1 What is already there, because a window wired the door

Option A's closing (`339f2042`) landed **everything option B would need for
a rule's pass to exist at all**:

| What | Where | What it gives option B |
| --- | --- | --- |
| `verify_claim(context, evidence_id, *, check)` | `application/evidence.py:508` | **The operation.** It is the one caller of `advance` in `src/` (`application/evidence.py:590`) and it runs the check the caller names. A pipeline-driven verification would *call this operation*, not the store. |
| The refusal vocabulary | `application/refusal.py` — `verification_refused` | A refusal a pipeline-driven failure can be reported as. |
| The store's `advance` | `evidence/store.py:466` | The only writer of the status; it runs the check, appends the verdict, and judges the preconditions. **Unchanged by option A and unchanged by anything option B would need.** |
| `LabCairnIndex` | `evidence/index.py:554` | The `SourceIndex` implementation `advance` needs (`application/evidence.py:594`). |
| The gate's re-verification | `evidence/gate.py:367` (`_reverify`) | The gate already re-runs the logged checks and compares, so a pipeline-driven pass is checked twice: once when it was earned, once when a report cites it. |
| The status is citable | `evidence/states.py:87` (`CITABLE_STATUSES`) | A rule-backed record can be cited by a report. |

**This is a real reduction in option B's cost, and the record above does not
say it.** Option B was written when the tree had no verify door; the door
exists now. **A pipeline-driven verification would not need to invent a
writer, a check-runner, an index, a refusal or a citable status. It would
need to reach `verify_claim` and give it an `evidence_id` and a `CheckKind`.**

### 2.2 What is not there, and would have to change

| What | Cost | Why |
| --- | --- | --- |
| **The run's knowledge of which record it is about** | `AnalysisRunArgs` (`src/labcairn/security/capabilities.py:279-299`) has no `evidence_id` field; `AnalysisRequest` (`src/labcairn/analysis/service.py:278-296`) and `FigureRequest` (`application/analysis.py:87-104`) have none either. Adding one changes the closed argument model, the arguments digest, what a person sees when consenting, and every caller that builds the arguments. | **The run cannot be told what to verify.** Nothing in a run's request names a record. |
| **A consent for the verification** | The `analysis.run` approval is spent on the analysis. A write to the evidence ledger is a different act. Either the record id joins the approved arguments (above), or the verification needs its own capability — and `CapabilityId` is closed, with an unknown id a denial (`src/labcairn/security/capabilities.py:15-17`). | **The pipeline's consent does not cover a ledger write.** A verification that ran under the analysis's consent would be a write the person did not approve. |
| **A caller of `verify_claim` that is not a person** | `verify_claim` is called by the CLI (`task claim-verify`) and the API (`POST /records/{evidence_id}/verify`). | **The operation exists and is layer-correct; what is missing is the pipeline's call site and the record id to pass it.** |
| **A rule that can read a derived number** | C1/C2/C3 all need anchors; a computation locator cannot be anchored (`material/addressing.py:172-179`, `db/models.py:925-930`) and a derived number has no extracted span, no anchored cell and no unit/tolerance. | **A pipeline result is not something the ledger's rules can judge.** This is the deepest gap and it is *not* closed by the door. |
| **A manifest-to-record link** | `DerivationTargetKind.EVIDENCE_RECORD` exists (`src/labcairn/reports/receipt.py:109`) and **nothing writes it**; the manifest's receipt writes one `MATERIAL_FILE` ref (`src/labcairn/analysis/manifest.py:603-609`). | The shape is there; the link is not. Writing it would be a small change — but it would make the figure depend on a claim, and the artifact ledger's staleness rules would then apply to that link (`src/labcairn/reports/receipt.py:31-40`). |
| **The pipeline's own writes** | `UnitOfWork` has no evidence-record write helper (`src/labcairn/db/repository.py:169-229`); `artifacts` has no such column (`0001_initial_task_store.py:174-215`). | Only matters for attachment point A. Point B needs none of it. |

**The cheapest coupling, stated in one sentence:** *a pipeline-driven
verification is an `application`-layer operation that calls
`verify_claim(evidence_id, check=...)` with an `evidence_id` the request
carries — and the tree already has every other part of it.* The expensive
part is not the write; it is that **a derived number has nothing for C1/C2/C3
to check**, so the rule would have to be new.

### 2.3 The contract that would move

Three contracts would move if the pipeline carried verification, and the tree
names where each lives:

1. **The capability contract.** `AnalysisRunArgs`
   (`src/labcairn/security/capabilities.py:279-299`) would gain an `evidence_id` — or a
   new capability would be registered. The registry is closed, the digest is
   taken over the arguments, and `tests/test_capability_registry.py`-class
   witnesses read it.
2. **The evidence contract.** ADR-0004 Contract 2 (`evidence/store.py:96-134`
   — `ALLOWED_TRANSITIONS`) and Contract 3 (the three checks). A new rule
   would be a new checker id in `evidence/catalog.py`, and the catalog is
   built from the check modules' own constants — so a new check module, or a
   re-shaping of the catalog.
3. **The threat model's contract.** **C14** (`docs/THREAT-MODEL.md:1058`) —
   *"no product operation runs the ledger's checks"* — is watched by
   `tests/test_threat_model.py:1326`, and a pipeline that ran a check would
   falsify it. **See §4: that witness is already red, for a different
   reason.**

---

## 3. The two sub-shapes of option B, and what each costs

The record above names two sub-shapes for the owner to choose between:
**keep** the machinery as a contract, or **remove** it. Each is costed below.
**Neither is recommended.**

### 3.1 Sub-shape B1 — keep it as a contract

**What it is:** the catalog, the preconditions and `CITABLE_STATUSES` stay
exactly as they are, and the record (and the docstrings) say that they are
the API a future pipeline wires into.

**What it costs:**

| Cost | Measured size |
| --- | --- |
| **Product code** | **None.** The machinery is already there and already correct. The verify door (`339f2042`) made the machinery *live* rather than *contractual*, which is a different thing: B1 as the record above describes it presupposes the door is not wired, and **the door is now wired**. B1's honest content on this tree is therefore *"the machinery stays, and the pipeline may wire into it later"* — which is a statement about the future, and the only thing it needs is that the statement be true. |
| **Witnesses** | **None new.** The witnesses that keep the surfaces honest already exist: `tests/test_surface_status_reach.py` (inverted by option A) watches that the operation is the one caller of the writer and that the status column's SQL lives only in the store. `tests/test_evidence_verify_door.py` (nine tests) drives the operation, the CLI and the API. |
| **Documents** | The record above's options section, and the docstrings' "this is the API a future pipeline wires into" sentence. **One caveat measured below:** the docstrings currently say the opposite — `application/evidence.py:55` describes `advance` as *"the ledger's only writer of that status, and it had no caller in the product"*, and the same file's `verify_claim` docstring (`application/evidence.py:518-524`) says the same. **Those sentences are now stale**, because the door exists. B1's documentary cost includes correcting them. |
| **The cost of B1 that is easy to miss** | **B1 does not preserve what the record above describes.** The record above's option B was written against a tree where `verified_by_rule` was unreachable and the machinery was dead. The door has since made it **reachable and live**. So B1 as written is *vacuous*: it says "keep the machinery as the API a future pipeline wires into", and the machinery is already the API a **present** surface wires into. **The owner would be choosing to keep a contract for a coupling that a window has already made real, by a route the owner chose (option A) but did not necessarily choose knowing this.** |

### 3.2 Sub-shape B2 — remove it

**What it is:** delete the `advance` preconditions' dead half, the
`VERIFIED_BY_RULE` members, and let the state machine carry five states.

**What it costs — and this is now much larger than the record above says,
because the door exists:**

| Cost | Measured size |
| --- | --- |
| **The status member** | `VerificationStatus.VERIFIED_BY_RULE` (`evidence/states.py`, member of the six). `VERIFICATION_STATES` is frozen as data (`states.py:38`) and the SQLite CHECK reads it (`migrations/versions/0005_evidence_ledger.py:121-124` — `status IN ('conflicted', 'extracted', 'planned', 'unsupported', 'user_attested', 'verified_by_rule')`), as does the ORM (`db/models.py:1381-1384`). |
| **The state machine** | `ALLOWED_TRANSITIONS` (`evidence/store.py:102-134`) — the `EXTRACTED → VERIFIED_BY_RULE` edge and the `VERIFIED_BY_RULE → {extracted, conflicted, unsupported}` edges. |
| **The preconditions** | `_require_precondition`'s `VERIFIED_BY_RULE` branch (`evidence/store.py:715-735`) — the passing-entry rule and the catalog rule. |
| **The citable set** | `CITABLE_STATUSES` (`evidence/states.py:87-89`) — `{verified_by_rule, user_attested}` becomes `{user_attested}`. |
| **The report side** | `FINDING_STATUSES` (`reports/model.py:155-161`) — `{extracted, verified_by_rule, user_attested}` loses a member. `reports/checks.py:332` reads it. |
| **The record model's own refusals** | `evidence/record.py` — the status validator that refuses a record *constructed* with the status and no passing log entry. |
| **The surfaces** | `api/routes.py` (the `POST /records/{evidence_id}/verify` route), `api/contracts.py` (`RecordVerificationBody`, `ClaimVerified`), `cli/commands.py` (`task claim-verify`), `application/evidence.py` (`verify_claim`, 100+ lines), `application/refusal.py` (`verification_refused`), `application/__init__.py` (the export and the capability table's row), `web/src/api/generated.ts` (regenerated). **That is the whole of option A's closing, undone.** |
| **The schema** | **A new migration.** The `status` CHECK in `0005_evidence_ledger.py:121-124` names the six values, and it is not the head — the head is `0035_role_abstention_event.py`. Removing a member from the CHECK is a `drop_constraint`/`create_check_constraint` in a new revision, plus the ORM's `db/models.py:1381-1384`. **And existing rows matter:** a database holding a `verified_by_rule` row cannot have the CHECK narrowed under it. |
| **The witnesses** | **This is the largest single cost, and it is larger than the record above says.** The record above measured "thirty-one call sites across six files" at `58486d21`. **At this tree the count is 33 call sites of the store's `advance` across 8 files, of which 17 name `VERIFIED_BY_RULE`** (measured by AST, the same way the tree's own witness reads it). The `VERIFIED_BY_RULE` sites, file by file: `tests/test_evidence_store.py` (6), `tests/test_identifier_records.py` (5), `tests/test_evidence_gate.py` (3), `tests/test_analysis_report_checks.py` (1), `tests/test_application_evidence.py` (1), and `src/labcairn/application/evidence.py` (1 — the door itself). **Plus** the witnesses that would have to be rewritten rather than merely adjusted: `tests/test_surface_status_reach.py` (271 lines, inverted by option A; its whole subject is the door), `tests/test_evidence_verify_door.py` (562 lines, nine tests, all about the door), `tests/test_evidence_contracts.py` (the six-states witness, `test_verification_states_are_exactly_the_six_architecture_declares`), `tests/test_evidence_schema.py`, `tests/test_evidence_gate.py`, `tests/test_cite_c1.py`, `tests/test_cite_c2.py`, `tests/test_analysis_report_*.py` (seven files), `tests/test_api.py` (the mutating-surface set), `tests/test_status_consistency.py`, `tests/test_skill_contracts.py`, `tests/evaluation/manifest.py`. |
| **The documents** | `docs/THREAT-MODEL.md` (C14's wording and the §"What no surface does is run the ledger's checks" paragraph), `docs/ARCHITECTURE.md` (the six states), `docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md` (8 mentions), `docs/adr/ADR-0016-model-proposal-and-human-confirmation.md` (9 mentions), `docs/RELEASE-NOTES.md`, `docs/REVIEW-DOSSIER.md`, `docs/plans/` (three plans), `docs/handoff/CURRENT.md` (4 mentions), `docs/acceptance/` (several), and `web/src/api/generated.ts` + `web/src/test/fakeApi.ts`. |
| **The shard costs** | A new migration and a large test rewrite both mean the shard costs must be re-measured on a runner (`python .github/remeasure_shards.py <run-id>`). |
| **What removal would NOT cost** | The three checks C1/C2/C3 stay — C1 is the source-existence check the store runs at the door for citable records (`store.py:526`, `_require_source_still_supports`), C2 and C3 stay as the gate's re-verification. **Only the `verified_by_rule` status and its transition go.** |

**The honest summary of B2's cost on this tree: it is the removal of option
A, not of a dead half.** The record above priced B2 against a tree where
`verified_by_rule` was unreachable; the tree it would be cut from has a
working door, a live status, a citable report state and 17 call sites
constructing the state in tests. **B2's cost is dominated by undoing a
change the owner already chose.**

### 3.3 What the two sub-shapes cost side by side

| | **B1 — keep as a contract** | **B2 — remove** |
| --- | --- | --- |
| Product code | none | a new migration, the ORM CHECK, the state machine, the preconditions, the citable and finding sets, the record model's validator, and **the whole of option A's closing** (a surface, a route, an operation, a refusal, the TS client) |
| Witnesses | none new | **at least 20 test files**, of which two are entirely about the door (271 and 562 lines) and one asserts the six states against a literal set |
| Documents | the record above; plus **correcting the stale "it had no caller in the product" sentences** in `application/evidence.py` | the threat model, the architecture doc, two ADRs, the release notes, the review dossier, three plans, the handoff, several acceptance records, and the generated TS client |
| Runner work | none | a shard re-measure on a runner |
| **What it means for the owner** | *"the machinery stays, and it is already wired to a person-driven surface"* | *"the machinery goes, and with it the surface the owner chose on 2026-11-28"* |

**Neither is free, and the asymmetry is the measurement.** B1 is nearly free
*because* the door exists; B2 is expensive *because* the door exists. **The
option-B question the record above poses — "should verification live only
inside the analysis pipeline" — is, on this tree, no longer a question about
the pipeline at all.** It is a question about whether the door should be
undone, and the pipeline is not in it.

**And the pipeline's own answer, for the record:** §1.7 shows that the
ledger's rules cannot read a derived number, and §1.2 shows that the tree
already holds that a derived number is made checkable by its manifest rather
than by a check. **So "verification lives only inside the analysis pipeline"
is not a sentence this tree can currently make true at all** — not because
the pipeline is too small, but because a pipeline result is not a thing the
ledger's verification machinery has a word for. The pipeline's own answer is
in `src/labcairn/analysis/manifest.py:1-9`: *what makes a derived number checkable is not a check
but this document.*

---

## 4. A witness that is red on this commit

**This is the finding that contradicts the brief, and it is reported rather
than worked around.**

`tests/test_threat_model.py::test_no_product_operation_runs_the_ledger_checks`
is **red on this tree**, and it was red before this window began.

```
$ E:/LabCairn/.venv/Scripts/python.exe -m pytest tests/test_threat_model.py -q
FAILED tests/test_threat_model.py::test_no_product_operation_runs_the_ledger_checks
E  AssertionError: these product modules reach for the ledger's verification write, so a
E  surface now runs a check:
E    application/evidence.py:122
E    application/evidence.py:590
1 failed, 39 passed in 6.59s
```

**What the witness says** (`tests/test_threat_model.py:1326-1360`): it walks
every module under `src/labcairn/` except `evidence/store.py`, and asserts
that **no module imports or calls `advance` or `append_verification`**. Its
docstring: *"C14 — the product writes claims, but no surface verifies them ...
If a product module reached either, then a surface produced a verdict, and
the threat model's statement that the product's records stay `extracted` would
be false."*

**Why it is red:** option A's closing wired the door, and the witness that
option A **inverted** was `tests/test_surface_status_reach.py` — but **this**
witness, the threat model's, was not inverted with it. `git show
339f2042 --stat` lists `docs/THREAT-MODEL.md` as changed, and the change is
**one re-pointed line number** (`cli/commands.py:3269` → `3338`) — no words
changed. The threat model's own prose still says, at
`docs/THREAT-MODEL.md:795-798`:

> **What no surface does is run the ledger's checks.** `evidence.store.advance`
> is the only path to a verified state, and no module under `src/labcairn/`
> calls it — the records the product writes stay `extracted` until a test
> advances them.

**Every clause of that sentence is now false.** A surface does run the
ledger's checks; a module under `src/labcairn/` does call `advance`; and the
records the product writes no longer stay `extracted`. The threat model's C14
row (`docs/THREAT-MODEL.md:1058`) still reads *"no product operation runs the
ledger's checks"*.

**And `application/evidence.py` still carries the same claim in its own
words**, twice, and one of them is load-bearing for a *different* operation
(`application/evidence.py:653-658`, inside `confirm_proposal`):

> **Not on the proposal's log** — the store's own design is that the old row
> is *marked* and the new one carries the attestation, **and a product module
> writing the ledger's verification row is what the threat model's C14
> forbids.**

**That sentence is now false**, and it is false in a way that matters:
`confirm_proposal` **does** write the ledger's verification row — through
`attest`, which is the store's own writer of the attestation entry. The
witness's own error message says it: *"these product modules reach for the
ledger's verification write, so a surface now runs a check"*.

**But the two hits are one thing, not two — and this window checked.** The
witness's watch-list is `{"advance", "append_verification"}`
(`tests/test_threat_model.py:1340`), and replicating the witness's scan
exactly over `src/labcairn/` on this tree returns **two** hits, **both** of
them `advance`:

```
application/evidence.py:122  <- advance    (the import)
application/evidence.py:590  <- advance    (the call)
```

**There is no `append_verification` hit.** `git grep -n "append_verification"
-- src/labcairn/application/evidence.py` returns **no match**, and `attest`
is not on the watch-list at all.

**So the red has exactly one cause: option A's door.** The `attest` import
beside `advance` on the same import block
(`application/evidence.py:122-134`) is **not** a second cause, and the
witness's repair is a one-liner rather than a decision about two writes.
This is worth stating because the witness's error message — *"so a surface
now runs a check"* — invites the reading that two surfaces now do, and
**they do not**: `attest` writes a **C4** entry, and C4's only verdict is
`not_checked` (`evidence/store.py:570-574`: *"The attestation is logged as a
C4 entry. C4 is the check whose only verdict is ``not_checked``"*). **An
attestation is a person's word, not a rule's pass**, and C4 is excluded from
`UPGRADING_CHECKS` (`evidence/store.py:137-139`) — so `attest` cannot move a
record to `verified_by_rule`, and the witness correctly does not watch it.

**The repair is therefore: the threat model and this witness both have to
say what is now true** — that the product *does* run the ledger's checks,
through the one operation the owner chose, and that the door is the only
door. That is a decision about the document's wording, and **this window
does not make it**: `tests/test_threat_model.py` and `docs/THREAT-MODEL.md`
are not this window's files.

**What the integrating session needs to know before the batch's one run: this
is red now**, a red in the required checks fails the pull request, and the
repair is the owner's or the integrating session's call rather than this
window's.

**Measured at:** `7bcfe53952e969ee1736af3623a656927d550d62`, the tree this
window started from, which is also `main`'s tip. The red is **not** caused by
anything this window did — this window changed no file under `src/` and no
test.

---

## 5. What was measured, and how

**The tree:** `7bcfe53952e969ee1736af3623a656927d550d62` (`main`'s tip as
this window started, and this worktree branch's tip). The record above was
measured at `58486d21` and closed at `f39b96b3` + `339f2042`; where a number
is quoted from that tree, the tree is named.

**The interpreter:** `E:/LabCairn/.venv/Scripts/python.exe` — Python 3.12.13.
**The venv's editable install names the main checkout**, so every run below
was launched with `PYTHONPATH` pointing at this worktree's `src`; the
console script was checked to be loading this tree (the `task claim-verify
--help` command exists only here), which is the check the repository's own
rules ask for when a tree is not the installed one.

**The counts** were taken by an AST scan of the tree's own shape — the same
approach `tests/test_surface_status_reach.py` and
`tests/test_threat_model.py` use, so that a docstring mentioning `advance` or
a comment is not counted as a call. The scan resolved `advance`'s third
positional argument (the `to_status`) and read the status it names.

**The commands, and what they returned.** Status was read from the command
itself, never from a pipe.

| Command | Result |
| --- | --- |
| `git grep -n "^from labcairn\.\(evidence\|db\|reports\)" -- src/labcairn/analysis/` | 6 lines; none from `labcairn.evidence` |
| `git grep -n "evidence_id\|EvidenceRecord\|record_id" -- src/labcairn/analysis/` | no match |
| `git grep -n "EvidenceKind" -- src/labcairn/analysis/` | no match |
| `git grep -n "EVIDENCE_RECORD" -- src/` | 3 lines, all the definition and its docs; no constructor |
| `git grep -n "labcairn.analysis" -- src/labcairn/evidence/` | no match |
| AST scan of `advance` call sites (this tree) | 33 call sites, 8 files; 17 name `VERIFIED_BY_RULE` |
| AST scan of `advance` call sites (at `58486d21`) | 31 call sites, 6 files; 16 name `VERIFIED_BY_RULE` — **the record above's "thirty-one call sites across six files" is confirmed at its own commit** |
| `pytest tests/test_threat_model.py -q` | **1 failed, 39 passed** — the C14 red of §4 |
| `pytest tests/test_surface_status_reach.py tests/test_evidence_verify_door.py -q` | 13 passed |
| `pytest tests/test_threat_model.py -k no_product_operation_runs_the_ledger_checks -q` | 1 failed (the same red, isolated) |

**What was not measured:**

* **No run of the analysis pipeline was driven.** The pipeline's shape was
  read from its source; the measurements above are of what the code says, not
  of a run's behaviour. A witness that drove a run end to end would be the
  way to confirm that the seven steps happen in that order.
* **The gate's re-verification of a rule-backed record was not driven.** §1.7
  reasons from C3's own refusals, not from an executed C3 against a record
  with no anchors.
* **No timing was taken.** This record costs no wall clock: it is a read of
  the tree plus two test runs.
* **The threat model's C14 repair was not designed.** §4 names the red and
  its single cause; it does not say what the threat model should say,
  because that is a decision about the document's meaning.
* **The pilot's corpus was not read**, and no model request was made.

---

## 6. What this record does not decide

* **Which option the owner should want.** Not B, not B1, not B2. The record
  above was neutral about the options; this one is neutral about the
  sub-shapes, and §3.3 says only what each costs.
* **Whether the door should stand.** §4 reports that the threat model's
  witness is red, and the repair is the owner's or the integrating session's
  call.
* **Whether the pipeline should ever carry verification.** §1.7 says the
  tree's rules cannot read a derived number today; that is a measurement of
  the tree, not a recommendation against the idea.
