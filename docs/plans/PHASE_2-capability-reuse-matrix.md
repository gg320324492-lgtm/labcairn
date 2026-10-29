# Phase 2 — capability reuse matrix

**Date:** 2026-10-29 · **Base commit:** `66dde87` (the merge of PR #125) ·
**Scope:** what Phase 1 already provides that Phase 2's mentor-trajectory
mainline can build on, what must be extended, and what must **not** be reused.

**How to read this.** Each row names the code, the test that watches it, and
the commit the reading was made at. A row marked *extend* names what is
missing. A row marked *cannot* names the reason, and the reason is always a
property of the code rather than a preference — the project's own rule is
that a decision needs a witness, and a witness needs a thing to break.

**What this matrix is not.** It is not a plan, and it does not approve
anything. It is the inventory the design's §1 asks for before code: *"a
capability reuse matrix: existing / needs extension / cannot be reused, with
file, class or function, tests, and SHA."*

---

## 1. The three answers, and the short version

| Verdict | Count | What it means |
|---|---|---|
| **Reuse** | 9 | the code exists, is tested, and Phase 2 uses it as it is |
| **Extend** | 8 | the vocabulary or the shape exists; the behaviour does not, and Phase 2 builds it in place |
| **Cannot** | 6 | using it as-is would violate a boundary ADR-0003/0004 already set |

The single most important row is **§3.3 — the evidence creator
`model_proposal`**: the vocabulary for "a model's say-so is not evidence"
**already exists in the schema, is already named in the code, and has never
been used**. Phase 2's central scientific claim — that a guidance suggestion
is a proposal awaiting human confirmation, not a finding — has a home to live
in that Phase 1 already carved out. That is the strongest reason this
project, and not a new one, is the right place to build Phase 2.

---

## 2. Reuse as it is

### 2.1 The task/run/stage/operation spine

| | |
|---|---|
| **Where** | `src/labcairn/db/models.py:281-412` (`tasks`, `runs`, `stages`, `operations`), `src/labcairn/runtime/` |
| **Watched by** | `tests/test_runtime_contracts.py`, `tests/test_store_persistence.py`, `tests/test_store_atomicity.py`, `tests/test_store_concurrency.py` |
| **Verdict** | **reuse** |

Phase 2's `PaperProject` is proposed as an object *under* a Task, not a
parallel hierarchy. This row is the reason that proposal is sound: the
transactional unit of work, the run's durability, the stage's refusal
semantics and the operation's consent binding all already exist and are
tested. A Phase 2 that invented its own execution spine would have to
re-implement crash recovery, the uncertain-state discipline and the event
stream — all of which the project's own review history shows is where the
hard parts are.

### 2.2 The append-only event stream

| | |
|---|---|
| **Where** | `src/labcairn/runtime/event.py:39-77` (`EventType`), `src/labcairn/db/models.py:556` (`events`) |
| **Watched by** | `tests/test_event_payload_vocabulary.py`, `tests/test_store_events.py` |
| **Verdict** | **reuse, with one addition (see §3.1)** |

The closed vocabulary is the point: *"An unknown value is rejected, never
coerced"*, because a type this build has never heard of means a newer writer
produced it. Phase 2's new event types are **additions to a closed set**, and
adding them is the documented way to extend the system — not a second event
log.

### 2.3 The consent and approval machinery

| | |
|---|---|
| **Where** | `src/labcairn/security/approval.py`, `src/labcairn/security/policy.py`, `src/labcairn/security/capabilities.py`, `src/labcairn/recovery/approvals.py:100` (`ApprovalStore`) |
| **Watched by** | `tests/test_security_approval.py`, `tests/test_application_approvals.py`, `tests/test_recovery_approvals.py`, `tests/test_recovery_crash_matrix.py` |
| **Verdict** | **reuse the machinery; the row is extended by LC-P2-02** |

The single-use guarantee is one conditional `UPDATE` —
`recovery/approvals.py:328` `conditional_spend()` — and the module explains
why it is not inlined: *"the test that was supposed to prove the predicate
load-bearing re-implemented the statement in the test file instead of
calling it — so deleting the predicate from the product left the suite
green."* Phase 2 must not write a second approval path. The design says this
too ("*a ticket that mints its own approval has shipped an authorisation
bypass*"), and the ledger's refusal vocabulary already names
`capability_unregistered`, `policy_changed` and the rest.

**The gap is measured and confirmed:** `ApprovalRow`
(`db/models.py:415-447`) carries `capability`, `resource_key`,
`args_digest`, `state`, `expires_at`, `granted_at`, `consumed_at`,
`schema_version` — and **no grant-time policy digest and no bound-source
column**. `ApprovalStore.consume` takes `policy_digest_at_grant` and
`sources` **as arguments** (`recovery/approvals.py:216-219`) rather than
reading them from the row. PR #125's LC-P2-02 states this and the statement
is correct. Migration head is `0008_c2_profile`; the fix needs `0009`.

### 2.4 The capability registry

| | |
|---|---|
| **Where** | `src/labcairn/security/capabilities.py:59` (`CapabilityId`), `:299` (`CAPABILITIES`), `:370` (`MODEL_REQUEST`) |
| **Watched by** | `tests/test_capability_namespaces.py`, `tests/test_security_policy.py`, `tests/test_cli_refusal_enumeration.py` |
| **Verdict** | **reuse** |

The registry already holds **`MODEL_REQUEST`** with its own argument model
(`ModelRequestArgs`, `capabilities.py:262`). Phase 2's model call does not
need a new capability id, and *must not* mint one: the registry is what
`assert_capability_registered` checks before a consent is spent, so a
private capability id would be an authorisation bypass wearing a new name.

**`MODEL_REQUEST` is the only capability with `effect=Effect.NETWORK`**, and
the source says why: *"The only NETWORK capability. Being the only one is the
point of §C6.4"* (`capabilities.py:370-378`). ADR-0003 C6.4 is therefore not
a general rule Phase 2 can extend at will — it is a rule about **one**
capability, and it is the reason the phase's outbound path is a single
choke point rather than a family of them.

Phase 2's **new** capabilities (reading a manuscript version, archiving a
file, recording a guidance card) go in this same registry, in this same
namespace discipline — `docs/adr/ADR-0006-capability-namespaces.md` — and
their refusal reasons join the existing enumeration.

**The consequence for the design's data-egress rule.** The design requires
that *"sending material to a designated external inference service" is a
separate consent from "internal storage and parsing"* — an
`AccessGrant`-style permission that is not an approval of a *task
operation*. That is a **second kind of authorisation**, and it does not
belong in the operation-approval table at all: an approval says "this
operation may do this thing once, now", while a data-egress permission says
"this material may ever leave the machine, for these purposes".

The two must not be merged. If the egress permission were modelled as a task
approval, then a granted approval to run one operation would be
indistinguishable from a standing permission to transmit the corpus — and the
design's default-deny for training and for third-party transmission would
have no representation at all. ADR `dataset-consent-and-access` has to decide
this, and the reuse matrix's finding is that **the registry has room for it
(`Effect` already distinguishes `NETWORK` from local effects) and the
operation-approval table does not.**

### 2.5 The source, locator and addressing model

| | |
|---|---|
| **Where** | `src/labcairn/sources/source.py:88` (`SourceKind`), `src/labcairn/sources/locators.py:65` (`LocatorKind`), `src/labcairn/material/addressing.py:112` (`render_locator_key`), `src/labcairn/db/models.py:674,836,1059` (`sources`, `source_texts`, `source_anchors`) |
| **Watched by** | `tests/test_source_contracts.py`, `tests/test_material_addressing.py`, `tests/test_material_schema.py`, `tests/test_source_id_type.py`, `tests/test_evidence_anchor_registry.py` |
| **Verdict** | **reuse the model; extend the vocabulary (see §3.2)** |

The lesson this model already encodes is the one Phase 2 most needs:
*"Review found four spellings of one page coexisting as four rows before this
existed"* (`material/__init__.py`). A `RevisionEvent` that cannot be located
back into its source file is not evidence. Phase 2's anchor requirement —
*every change must be clickable back to the original DOCX* — is the same
requirement the `locator_key` already serves for pages and cells.

### 2.6 The material ingestion path

| | |
|---|---|
| **Where** | `src/labcairn/material/ingest.py`, `walk.py:101` (`ingest_workspace`), `indexing.py:71` (`build_index`), `version.py:78` (`derive_extraction_version`) |
| **Watched by** | `tests/test_material_ingest.py`, `tests/test_material_indexing.py`, `tests/test_material_walk.py`, `tests/test_material_regressions.py` |
| **Verdict** | **reuse** |

Three things Phase 2 gets for free:

- **Content addressing.** Bytes are hashed and stored by hash; the workspace
  walk records *where* the material is, not the key it was handed.
- **Readability as a distinct state.** `SourceReadability` separates "we
  could not look" from "there was nothing there" (`sources/source.py:104`).
  Phase 2's "the revision exists but its author is unknown" needs exactly
  this discipline, and it is already the project's.
- **Derive the extraction version from the source.** `material/version.py`
  derives `extraction_version` from the adapter's own module source, so
  changing extraction code changes the version without anyone remembering to
  bump a constant. **Phase 2's OOXML parser must do the same**, or a
  re-parse of the same file will look like a different document for no
  recorded reason.

### 2.7 The evidence ledger

| | |
|---|---|
| **Where** | `src/labcairn/evidence/record.py`, `states.py:50` (`VerificationStatus`), `gate.py`, `store.py`, `index.py` |
| **Watched by** | `tests/test_evidence_contracts.py`, `tests/test_evidence_gate.py`, `tests/test_evidence_store.py`, `tests/test_evidence_schema.py`, `tests/test_cite_c1.py`, `tests/test_cite_c2.py`, `tests/test_cite_c3.py` |
| **Verdict** | **reuse** |

The gate refuses **as a whole**: "`citable` is empty when any record fails,
because a partial list would invite a caller to cite the ones that survived."
Phase 2's guidance cards inherit that: a card whose evidence does not
resolve is not a card with fewer citations, it is **no card**.

The conflict rule matters for LC-P2-11: *"A conflict is handed over as data
with two interchangeable sides, so the structure itself cannot express a
winner."* That is precisely what the design asks for with contradictory
advisor rules and reviewer feedback — *"禁止按较新时间自动选赢家"*.

### 2.8 The refusal vocabulary and the exit-code discipline

| | |
|---|---|
| **Where** | `src/labcairn/application/refusal.py`, `src/labcairn/security/policy.py`, `src/labcairn/cli/` |
| **Watched by** | `tests/test_refusal_witnesses.py`, `tests/test_cli_refusal_enumeration.py`, `tests/test_cli_path_refused_catch.py` |
| **Verdict** | **reuse** |

Every refusal is one type with a machine-readable reason and a message that
names what is wrong. Phase 2 has many more refusals to express ("this
comment has no anchor", "this version's parent is unknown", "this material
is not authorised for training"), and they all join this vocabulary. A new
refusal type is a new row in the enumeration **and** in the CLI's rendering —
the project watches that the enumeration and the CLI agree
(`test_cli_refusal_enumeration.py`).

### 2.9 The report and the four renderers

| | |
|---|---|
| **Where** | `src/labcairn/reports/model.py`, `build.py`, `checks.py`, `revisions.py`, `render/` (markdown, html, docx, pdf) |
| **Watched by** | `tests/test_analysis_report_build.py`, `tests/test_analysis_report_checks.py`, `tests/test_analysis_report_revisions.py`, `tests/test_analysis_report_manifest.py` |
| **Verdict** | **reuse, with one semantic separation (see §4.1)** |

The report path already assembles what a task has: *"a record that may be
stated becomes a claim and one that may not becomes a disclosure"*
(`application/reports.py`). That is the shape a guidance card needs. And the
DOCX renderer already exists — which means the project can **write** DOCX,
and Phase 2's task is to **read** the revision history out of one.

---

## 3. Extend: the vocabulary exists, the behaviour does not

### 3.1 A new event family for the trajectory — `EventType` extension

`EventType` is closed by design, and additions are the sanctioned way to
extend it. Phase 2 needs a family for revision observation, and **the
decision on its exact members belongs in the ADR**, not here. What this row
fixes is the *shape*: these are **task-level or operation-level annotations**,
not state transitions — they record that something was observed, and they
must not be able to change state. The existing precedent is the three
annotation events (`ARTIFACT_RECORDED`, `SOURCE_CHANGED`,
`OUTBOUND_CONSENT_REQUESTED`, `runtime/event.py:74-76`), which are
deliberately outside the transition families.

### 3.2 A DOCX source kind — `SourceKind` extension

`SourceKind` (`sources/source.py:88`) is `PDF | MARKDOWN | TEXT | CSV |
XLSX | OTHER`. **There is no DOCX.** `OTHER` exists for files that "can be
inventoried and hashed, just not cited" — so today a Word file can enter the
store and be hashed, and cannot be addressed. Phase 2 needs DOCX to be a
first-class kind with a `LocatorKind` of its own, because a revision event's
anchor is *not* a page, line, row or cell — it is a **character range inside
a paragraph inside a part**, and `LocatorKind` is CHECK-constrained to the
existing four extractable kinds.

**Why this cannot be done by widening `LocatorKind` loosely:** the
constraint on `source_anchors.locator_key` is what stops a locator naming
something that cannot exist, and the report's link check
(`analysis_report_checks`) resolves every citation against the material and
acts on the answer. A DOCX locator that can be *written* but not *resolved*
would put a citable claim on an address that resolves to nothing.

### 3.3 `model_proposal` — the creator that has never been used, behind a check that already works

| | |
|---|---|
| **Where** | `src/labcairn/evidence/states.py:96-112` (`EvidenceCreator.MODEL_PROPOSAL`), `src/labcairn/evidence/states.py:50-76` (`VerificationStatus`, six states), `src/labcairn/evidence/record.py:363-371` (the constructor check), `src/labcairn/application/evidence.py:44` |
| **Watched by** | `tests/test_evidence_contracts.py`, `tests/test_evidence_schema.py` |
| **Verdict** | **extend — and this is Phase 2's most important reuse** |

The application's own comment says it: *"model_proposal exists so a future
proposal path is expressible; it is not [yet exercised]."* Phase 1 carved
the slot out and left it empty.

This is the whole of the design's central scientific discipline, already
expressed in the schema: **a model's say-so is a `model_proposal`, and it
cannot become `verified_by_rule` without a rule that checks it and a human
who attests it.** ADR-0004 says the same in prose ("*a model's say-so is not
evidence*"), and LC-P2-12's `GuidanceCard` is exactly this shape.

**The read of the tree is stronger than the design assumes, in two ways.**

1. **The status machine is a six-state machine, not three.**
   `VerificationStatus` is `PLANNED | EXTRACTED | VERIFIED_BY_RULE |
   USER_ATTESTED | CONFLICTED | UNSUPPORTED`, and its docstring says why the
   negative states exist: *"A design with only `planned` and `verified`
   cannot express either"* — ADR-0004 A3 (a paraphrase presented as a quote
   does not reach `verified_by_rule`) and A5 (neither side wins by recency;
   the conflict is displayed). **`conflicted` and `unsupported` are the
   states Phase 2's response-link model needs**, and they already exist.

2. **The creator check is already implemented, at construction.**
   `EvidenceRecord`'s validator refuses `user_attested` unless
   `created_by is EvidenceCreator.USER`, with the reason stated in the error
   itself: *"An attestation is something a person did; a rule or a model
   proposal reaching this state would misreport who stands behind the
   claim."* The refusal is at construction, in every path, including a
   hand-written JSON file.

**So the work is smaller than it looks, and the risk moves.** It is not
"invent a proposal concept"; it is (a) make the existing creator the path a
guidance suggestion actually takes, and (b) **make sure Phase 2's own path
cannot bypass the constructor check by writing the creator field directly.**
That second half is the new risk, and it is a Phase 2 witness rather than a
Phase 1 one: a mutation that writes `created_by=USER` for something a model
said would leave every Phase 1 test green, because the constructor is
checking a field the mutation overwrites before the constructor sees it.

**One constraint the `verified_by_rule` member states in its own comment:**
*"A rule confirmed a **number or a structure**. It never confirms a scientific
hypothesis."* Phase 2's guidance cards are scientific hypotheses about a
manuscript, so a rule may verify their structural facts and never their
scientific claims. ADR-0016's C13 is the witness for that line.

### 3.4 The DOCX *writer* already exists — the DOCX *reader* does not

`python-docx` is a declared dependency (`pyproject.toml`, LC-P1-11's report
export), used by `reports/render/docx.py:65`. It **writes** documents. It does
not read revisions: `python-docx` gives no access to `w:ins`, `w:del`,
`w:moveFrom`, `w:moveTo`, `w:commentRangeStart` or `w:commentReference` as
first-class objects.

So Phase 2 needs a **new read path** — a raw OOXML reader over the ZIP's XML
parts — and it must be a *new adapter* in the `material` package's own
registry (`material/units.py:251` `adapter_for`), so it inherits the
readability states, the addressing and the derived extraction version. This
is an **extension of an existing mechanism**, not a new subsystem.

### 3.5 The approval row — the two missing columns

See §2.3. The work is a migration (`0009`) plus reading the policy digest
and the bound sources **from the row** rather than taking them as arguments.
`Migration` head is `0008_c2_profile`; the existing
`tests/test_store_migrations.py` and the parity test in
`tests/test_evidence_schema.py` (which walks `Base.metadata` and the migrated
schema independently) will catch a migration that adds a column to one and
not the other.

### 3.6 The provider path — three protocols, no product operation

`src/labcairn/providers/` speaks three real protocols and probes four
capabilities; `CapabilityId.MODEL_REQUEST` and `ModelRequestArgs` exist. But
the design's claim is verifiable in the tree: **no stage of the shipped
`research-report` Skill calls a model**, and the only code that sends a real
request is the probe. LC-P2-01 extends the existing provider layer; it does
not build a client.

**A measured constraint the design records and the tree supports:** the
probe's answer (2026-10-28, `MiniMax-M3.1-Flash`) is that `tool_calls` and
`usage_reporting` work and **both structured-output forms are declined by the
client**, inside `pydantic-ai` before a request is sent. A Phase 2 design
that assumes native structured output starts from a refusal. This is why the
design's data contract (§5) is a *schema in the repository* rather than a
"the model returns JSON" assumption.

### 3.7 The retrieval corpus — three papers

`tests/fixtures/retrieval/ground_truth.json` is a human reading of **three**
papers, and the protocol's `evidence-locator-validity` metric is
`NOT MEASURED`. Phase 2's mentor-experience retrieval (LC-P2-11) inherits
that ceiling: **there is no corpus in this tree large enough to say whether a
retrieval change is a gain.** LC-P2-05 is the ticket that changes it, and it
is a precondition for LC-P2-11's measurement rather than a parallel concern.

### 3.8 The workbench — three surfaces that do not yet read the event stream

The web workbench exists and is tested (`web/src/app/`), but its own
recorded limits are: the event stream is not consumed by the UI, it cannot
switch the selected project, and it is never driven against the live service.
Phase 2's "click a mentor comment → see the change → see the response"
interface lands on this workbench, so **the first thing Phase 2 must do to
the workbench is consume the event stream it already has.**

---

## 4. Cannot be reused, and why

### 4.1 Report revisions are not manuscript revisions

`reports/revisions.py` versions a *report*. `ReportRevision` answers "which
report, which revision, is it stale". A manuscript version answers "which
draft, which round, who wrote it, what changed". **The two are different
semantics and the design says so** ("*勿混用报告修订与手稿修订两种语义*").

Reusing the report's revision model for manuscripts would produce a table
where "revision 3" means two different things in two places. Phase 2's
`PaperVersion` is a **new table**; the report's revision chain is not
extended to cover it.

### 4.2 The single-user scope label is not an access control

`tasks.owner_id` exists so that two questions are answerable from the schema
rather than from convention: whose Task this is, and what a future multi-user
migration has a column to populate. Its own docstring says: *"owner_id is not
authentication and must never be presented as one — it carries no secret and
authorises nothing."*

Phase 2's data-governance ADR (LC-P2-06) needs the same distinction to hold
in the other direction: **a `paper_project.owner_id` would be a scope label
too, and the design's cross-student isolation requirement cannot be met by
it.** Either a real ACL is designed, or the pilot is single-user and says so.
The design's §8 and §12 both land on this: *"不能把 Phase 1 的 loopback
Web 直接开放到课题组局域网或公网"*.

### 4.3 The trigram index is not a semantic index

`evidence/index.py` builds an FTS5 index on a **trigram** tokenizer
(migration `0006`), and the index build reports what it excluded
(`material/indexing.py:204`). Trigrams find lexical overlap. They do not find
*"a mentor who said this about method design in a different discipline"*.

LC-P2-11's case retrieval needs semantic matching over guidance cases. That
is **either** an extension of the existing index with a second ranking signal
— reusing the index's exclusion reporting and its miss semantics — **or** a
separate retriever. The design's rule is that a query the index cannot serve
is reported as a **miss, not an answer**; Phase 2 inherits that exactly.

### 4.4 `ArtifactLedger` is in memory

Phase 1's ledger does not survive a restart, though the store does — a
recorded carried limitation. Phase 2's guidance memory (§ LC-P2-11) is
**long-lived by definition**: a rule that a restart forgets is not a rule, and
a rule that is withdrawn must be withdrawable. **Phase 2's memory must be
stored, not ledgered.** The same durability shape as LC-P2-02 on the
artefact side.

### 4.5 `ApprovalLedger` is in memory — and it is the *safe* direction

The in-memory ledger's emptiness after a restart means a granted approval
fails closed with `APPROVAL_MISSING` rather than double-spending. That is
LC-P2-02's characterisation, and it is correct: **today's behaviour is a
durability feature, not a safety hole.** Phase 2 must not "fix" this by
making approvals survive in memory.

### 4.6 The out-of-the-box PDF adapter is not a PDF annotation adapter

`material/pdf.py` reads **text** from PDFs with `pdfplumber` +
`pdfminer.six` (ADR-0008, both MIT), and it **refuses** a two-column page
rather than splicing columns — *"splicing two columns stores sentences the
author never wrote"*. That refusal is a feature.

The design wants a PDF *annotation* adapter for LC-P2-13's reviewer comments.
A PDF's annotations are a different thing from its text: they live in the
annotation objects, they have their own author and date, and they are
**not** recoverable into a Word revision history. Phase 2 gets a new
adapter; it does not extend the text adapter, and the new adapter inherits
the same refusal discipline for pages it cannot read.

---

## 5. What this matrix implies for the first gate

1. **Nothing in Phase 2 needs a new execution framework.** §2.1, §2.2, §2.3
   and §2.6 cover the whole spine. The design's "do not build a second
   Agent framework" is not a preference here; it is what the matrix shows.
2. **Three things must be built rather than extended**, and they are the
   three the design names as its technical hurdles: a DOCX OOXML reader
   (§3.2, §3.4), a version graph (§4.1), and a response-link model.
3. **Two vocabulary slots exist and are empty** — `model_proposal` (§3.3) and
   `OUTBOUND_CONSENT_REQUESTED` (`runtime/event.py:76`, declared and never
   emitted). The design's ADR `model-proposal-and-human-confirmation` and the
   Phase 1 carried limitation "ADR-0006's outbound-consent bridge is not
   built — both modules exist, nothing joins them" are the same fact seen
   from two sides.
4. **One measurement ceiling is inherited**: the retrieval corpus is three
   papers (§3.7). LC-P2-14's ablation cannot be run until LC-P2-05 has
   widened it.

---

## 6. Verification of this matrix

Every claim in §2–§4 names a file and a line. The ones that matter most were
checked against the tree at `66dde87`:

| Claim | How it was checked |
|---|---|
| `SourceKind` has no DOCX | `sources/source.py:88-101`, read in full |
| `model_proposal` is declared and unused | `grep -rn MODEL_PROPOSAL src/` → 2 hits, both declarations plus one comment saying it is not exercised |
| `OUTBOUND_CONSENT_REQUESTED` is declared and un-emitted | `grep -rn OUTBOUND_CONSENT src/` → 2 hits, both in `runtime/event.py` |
| `ApprovalRow` lacks a policy digest and bound-source column | `db/models.py:415-447`, read in full |
| `consume` takes those as arguments | `recovery/approvals.py:207-220`, read in full |
| `CapabilityId.MODEL_REQUEST` exists | `security/capabilities.py:59-84, 370` |
| `LocatorKind` is constrained to four kinds | `sources/locators.py:65-77` |
| the event vocabulary is closed | `runtime/event.py:39-77` |
| fifteen tables exist | `grep -n __tablename__ db/models.py` → 15 |
| `python-docx` is declared | `pyproject.toml` dependencies block |
| the migration head is `0008_c2_profile` | `migrations/versions/` listing |

**What is not verified by this matrix.** No number in it was measured by
running Phase 2 code, because Phase 2 code does not exist yet. The
performance-related claims in §3.6 and §3.7 are quoted from the Phase 1
records they name (`RELEASE-NOTES.md` §2.13, the LC-P1-13 evaluation record)
and are marked as inherited measurements, not as measurements taken here.
