# ADR-0015: Dataset consent and access — four permissions, not one

**Status:** Proposed
**Work order:** LC-P2-06 (proposed; not yet dispatched)
**Date:** 2026-10-29

## Context and concrete problem

Phase 1 is a **local, single-user** application. `tasks.owner_id` exists, and
its own docstring is explicit about what it is not:

> *"`owner_id` is not authentication and must never be presented as one — it
> carries no secret and authorises nothing. It exists so that two questions
> are answerable from the schema rather than from convention: whose Task this
> is, and what a future multi-user migration has a column to populate."*
> (`db/models.py:78-93`)

Phase 2 changes what Phase 1 assumed. Two things arrive at once:

1. **Real, unpublished manuscripts.** A student's draft, their advisor's
   tracked changes and comments, their response letter, and possibly a
   reviewer's confidential report. None of this is published. Some of it is
   under a publisher's confidentiality terms, and a co-author may not have
   agreed to its use.
2. **A group's worth of people.** The teacher's goal is that a cohort can
   use the system. Phase 1's API binds to `127.0.0.1` and refuses a foreign
   origin; that is a correct design for one person on one machine, and it is
   **not** a multi-user access-control system.

The design's rule is blunt: *"不能把现有本地服务绑定到公网 IP，就当成课题组
平台"* — binding the loopback service to a LAN or public address does not make
it a group platform.

And the design's §8 raises the point that must be settled *before* any data
is collected, not after: the teacher is already collecting manuscripts from
students. **Every day of collection without a recorded consent is a day of
data held without a recorded basis.**

## The concrete problem this creates

Phase 1 has exactly one kind of authorisation: the **operation approval**.
An `ApprovalRow` says *"this capability may run once, on these arguments,
now, until this time"*, and the single-use guarantee is one conditional
`UPDATE` (`recovery/approvals.py:328`).

The design requires **four independent permissions**, and they are not
variants of each other:

| # | Permission | Default | Governs |
|---|---|---|---|
| 1 | **Store and read internally** | — | keeping the bytes and letting a named person read them |
| 2 | **Parse, annotate and retrieve offline** | — | running the extractors, the annotators, the index |
| 3 | **Send to a named external inference service** | **deny** | transmitting content to a third party |
| 4 | **Train on, and reuse in a shared research corpus** | **deny** | parameters, embeddings, checkpoints, datasets |

**The trap is that these look like one thing and are not.** Permission 3 and
4 are the two that carry consequences a student cannot undo, and both are
**default-deny** in the design. A system that models "consent" as one boolean
has, by construction, already granted 3 and 4 the moment somebody ticks
"yes" to 1.

**The second trap is that permission 3 and 4 are not operation approvals at
all.** The reuse matrix (§2.4) records the decisive fact: `MODEL_REQUEST` is
the **only** capability with `effect=Effect.NETWORK`, and the source says
why — *"Being the only one is the point of §C6.4"*. ADR-0003 C6.4 governs
one capability. An operation approval is the wrong instrument for a standing
data permission, because:

- an approval is **single-use** and **expires**; a data permission is
  standing and revocable;
- an approval binds to **one operation's arguments**; a data permission binds
  to **a class of material and a purpose**;
- an approval's answer is "may this run now"; a permission's answer is "may
  this material ever be used for this".

Merging them would make the two indistinguishable — and would leave the
default-deny for permissions 3 and 4 with **no representation at all**.

## Alternatives

### A. One `consent` boolean on the material

Simplest, and the model most systems reach for first.

**Rejected.** It cannot represent permission 3 or permission 4 being denied
while permission 1 is granted, unless it is tri-state, and a tri-state
boolean cannot express *"storage yes, parsing yes, transmission no,
training no"* — which is, per the design's §10, **the most common answer a
student will actually give.** A single bit would force the student to
answer "no" to everything, because the bit cannot hold the real answer.

### B. Reuse the operation-approval table for data permissions

**Rejected**, and this is the one the design's §3 forbids most explicitly
("*"不得将作者响应与审稿后录用等同于建议正确"* is a different rule, but the
same instinct: two different kinds of truth in one structure"). An approval
row is operation-scoped, single-use and expiry-bounded. A data permission is
material-scoped, standing and revocable. Putting the second in the first
means every query that asks "may I send this to a model?" has to reconstruct
a permission from rows that were never designed to hold one, and the default
becomes "the absence of a refusal is a permission" — which is exactly the
failure mode the project already refuses elsewhere (`sources/source.py:91`:
*"`OTHER` is for files LC-P1-08 ingests but Phase 1 cannot address"* — an
explicit state, not a silent default).

### C. A per-file permission set, stored beside the material

**Rejected.** Permission is a property of *a purpose and a body of
material*, not of one file. A student may allow parsing of the whole
archive but transmission of nothing, or transmission of the figures but not
the draft text. Per-file bits make the common case ("none of my files may be
transmitted") a rule about every file, which is exactly the rule that gets
forgotten when a new file arrives.

### D. A purpose-scoped grant table, with the four permissions as separate grants

**Chosen.** A grant names: the subject (a project or a body of material), the
**purpose**, the **permission**, the scope it covers, who granted it, when,
and how to withdraw it. The four permissions are four grant kinds, and each
is independently absent, present or withdrawn.

**A grant is not an approval.** It is a different table with a different
lifetime, and the two never appear in the same row.

### E. Do not collect any data until a multi-user system exists

**Rejected as a sequencing rule, and it is the tempting one.** The teacher's
students have already handed over files; refusing them the benefit while a
multi-user platform is designed is its own harm. And the design's V0
deployment (§12) is explicit: *"受控单机/校内服务器、离线文件接收目录、
单管理员+少量受邀标注者"* — a controlled single machine, an offline intake
directory, one administrator and a few invited annotators. **That does not
require a multi-user service**, and it is the shape Phase 2's pilot takes.

## Decision

### D1 — Four grant kinds, independently absent, independently withdrawn

```
AccessGrant:
  grant_id
  subject_ref        the paper project, or a body of material
  purpose            what the grant is for (read | annotate | retrieve | transmit | train)
  permission         store_read | parse_annotate | external_transmit | train_reuse
  scope              which material it covers
  granted_by         a named person
  granted_at
  expires_at         optional
  state              active | withdrawn | expired
  withdrawn_at       optional
  withdrawn_by
  withdrawal_reason
```

**Absence is denial.** A permission with no grant is denied, and the code
path that reads it must treat the missing row as a refusal, not as a
default-allow. The project's existing pattern for this is `ApprovalLedger`
after a restart: the ledger is empty, the spend **fails closed**, and the
refusal reason is machine-readable. The same rule applies here.

### D2 — `external_transmit` and `train_reuse` are default-deny and are refused by absence

Not "denied until granted" as a UI default — **denied in the model**. There
is no row, so there is nothing to check, so the path cannot proceed.

The design's §3 is explicit that these two are *"缺省拒绝"* (denied by
default), and the Phase 1 refusal vocabulary already has the shape this needs
(a machine-readable reason plus a message naming what is wrong).

### D3 — Transmitting is a *separate* gate from calling a model, and both must pass

A model request carries material. Therefore **two** independent checks run,
and passing one does not imply the other:

1. the **operation approval** for `model.request` (does this operation
   spend money and transmit?); and
2. the **`external_transmit` grant** for the material in the request (is this
   material permitted to leave the machine, for this purpose, to this
   destination?).

**The design's §12 says it directly: "向外部模型发送资料按'数据外发'审批，
而不只是'调用 API 的技术设置'"** — sending material to an external model is
approved as *data egress*, not merely as a technical API setting. A ticket
that wired only the first would send manuscripts to a third party on the
strength of an operation approval alone, which is the exact failure the
teacher's un-published drafts cannot survive.

**The destination matters.** The grant names the permitted recipient, so a
grant to one provider is not a grant to another. A model call that would
transmit to a destination the grant does not name is **refused**, with the
destination in the message.

### D4 — Withdrawal propagates, and propagation is checkable

Withdrawing a grant must invalidate what depended on it: derived embeddings,
index entries built from the material, queued training runs, cached model
transcripts, and any guidance rule distilled from it.

**The design's §7 names the hard case**: *"撤回同意后历史 embedding/缓存/训练
队列是否失效"* — after consent is withdrawn, do historical embeddings, caches
and training queues expire? The answer must be *yes*, and it must be
**demonstrated**, because a withdrawal that leaves a derived copy behind is
not a withdrawal.

This is the same discipline the project already holds for stale artefacts:
`invalidate_on_source_change` marks a figure and its manifest `STALE` with
the reason, and a run over changed bytes is refused.

### D5 — Identity information is stored separately from content

Names and email addresses of authors, advisors and reviewers are **personal
data** and are kept apart from the material and apart from the analysis
results. A pseudonymous subject id links them.

**`author_raw_private` is private by name and by contract.** The revision
event records the advisor's name as it appears in the file, because that is
the observation — but the field is marked private, it is excluded from
exports and reports, and the guidance rules that quote it reference the
event rather than embedding the name.

### D6 — The pilot is single-administrator and offline; the multi-user question is deferred with its conditions written down

Phase 2's pilot (P2-G5) is: **a controlled machine, an offline intake
directory, one administrator, a few invited annotators.** Not a LAN service,
not a public one.

**This is a decision with conditions, not an exemption.** The conditions are
recorded in `docs/plans/` as the design's §12 V1 asks: a real identity model,
row-level or application-level permissions, an audit trail, annotation
arbitration, institutional SSO or explicit separate accounts, and backup /
restore / withdrawal-deletion consistency checking — **and at least one
permission penetration test or a human security review before opening to
anyone.**

Until those exist, the Phase 1 security assumptions hold unchanged: the API
binds to loopback, refuses a foreign origin, and requires a session token.

### D7 — `owner_id` stays a scope label, and the new tables do not pretend otherwise

`PaperProject.owner_id` records *whose* project this is. It is not
authentication and it authorises nothing — exactly as `tasks.owner_id` is
not. The grant table is what authorises, and it names a **granted_by
person**, not an owner scope.

This keeps the reuse matrix's §4.2 honest: the pilot's isolation comes from
the *grants*, and the grants are checked by a real program, not by a column.

### D8 — Real material never enters the public repository, CI, or the evaluation corpus

The Phase 1 rules already hold this — the reference-exclusion workflow, the
secret scan, the outsider-path check — and Phase 2 adds a specific one:

**A permitted real manuscript is never committed, never uploaded by CI, and
never enters the public evaluation corpus.** The evaluation corpus for
LC-P2-14 is synthetic or separately authorised, and the private pilot set
lives outside the repository and outside every CI artefact.

**The whole-suite CI run is one of the places where real data leaks**, and
the project's own carried limitation about `httpx` being undeclared shows how
easily a dependency path becomes an egress path. LC-P2-01's provider path
must therefore be unable to reach a real material path by accident.

## Upstream evidence (reference only)

No upstream project was consulted for this ADR, and that is deliberate: it is
a governance decision about *this* lab's material, not a technical choice
between libraries.

What the upstream studies did contribute is negative evidence about how
easily provenance is lost:

- **arXivEdits** (`113913d68522c1c8428d8e191d5c9bed633da6ce`) — the corpus
  carries a **per-paper licence**, and it is a mixture of eight distinct
  licences, several non-commercial. This is the shape of the problem: even
  public scientific writing has heterogeneous permissions, and a private
  archive has more of them, not fewer. The repository ships **no licence
  file at all** for its code.
- **XtraGPT** (`9f4be5c69878b16b5836a3769745bd190b585572`) — the README
  asserts a model licence (MG0-2.0) that the repository **does not ship**,
  and points at a `LICENSE` file that is not there. A permission asserted in
  prose is not a permission that can be complied with, and this is the
  failure mode D3's "destination matters" is designed to avoid on our side.

Full records: `docs/research/upstream-study/`.

## Risks, tradeoffs and reversibility

**Risk — the grant table becomes a second approval path by accident.** A
Phase 2 operation that finds "the material is granted" and treats that as
"the operation is approved" would ship an authorisation bypass — the exact
thing LC-P2-01's draft warns about ("*a ticket that mints its own approval
has shipped an authorisation bypass*"). Mitigation: **the two tables have
different columns and different lifetimes, and the model-request path must
check both.** A witness must fail when either check is removed.

**Risk — over-collection.** The design warns that a student may hand over a
file they have no right to share (a co-author's draft, a confidential review
report). The grant table cannot detect that, and the intake process must
ask. This ADR does not solve it and does not pretend to: the design's §10
puts the burden on the intake conversation, and the "no rights" case is a
**refusal at intake**, not a later deletion.

**Risk — withdrawal is hard in practice.** Derived copies are hard to find.
Mitigation: D4 makes propagation a *checkable* property with a witness, and
the guide lists it as a negative test (*"撤回同意后历史 embedding/缓存/训练
队列是否失效"*).

**Tradeoff — more friction at intake.** Four permissions mean four
questions, and students will be annoyed. Mitigation: the intake UI states the
**defaults** prominently — *"storage and parsing: yes; transmission to a
third party: no; training: no"* — so the common case is one click, and the
deviation is the deliberate act. The design's §10 asks for exactly this: each
item chosen independently, revocable, recorded.

**Reversibility.** The grant table is additive. Withdrawing every grant
returns the system to a state where no material may be used, and the
material can then be deleted with the propagation rule still enforced.

## Contracts and acceptance tests

| # | Contract | Witness |
|---|---|---|
| C1 | Material with no grant is **not readable** for the restricted purpose, and the refusal names the missing permission | to be written at LC-P2-06 |
| C2 | `external_transmit` with no grant refuses an outbound model request, **and the refusal does not spend the operation approval** | to be written at LC-P2-01/06 |
| C3 | An `external_transmit` grant naming provider A does not authorise a request to provider B | to be written at LC-P2-01/06 |
| C4 | An `external_transmit` grant on the material is refused when the request's material set includes material outside the grant's scope | to be written at LC-P2-01/06 |
| C5 | `train_reuse` with no grant excludes the material from every training queue, embedding index and derived corpus | to be written at LC-P2-06 |
| C6 | Withdrawing a grant invalidates the embeddings, index entries, cached transcripts and queued runs derived from that material | to be written at LC-P2-06 |
| C7 | A granted `store_read` plus a denied `external_transmit` is representable, and the denial survives a restart | to be written at LC-P2-06 |
| C8 | The `owner_id` of a project authorises nothing: setting it does not grant any permission | to be written at LC-P2-06 |
| C9 | No real manuscript's bytes, text, comment or metadata appear in the repository, in any CI artefact, or in the public evaluation corpus | to be written at LC-P2-06 |
| C10 | A withdrawal is recorded with a reason and an actor, and the record is not deletable by the withdrawing party | to be written at LC-P2-06 |

**C2 is the one to watch.** It is the difference between "the model call is
approved" and "the data may leave the machine", and a mutation that removes
the egress check while leaving the approval check would leave the suite green
unless C2 exists and is mutation-checked.

## Re-evaluation trigger

1. The teacher decides on a shared multi-user server, or on hosting the
   pilot off the teacher's machine. D6's conditions then become
   prerequisites, and a separate ADR for identity and row-level access is
   required **before** the pilot opens.
2. Any model provider is added to the workspace's `providers.json`. D3's
   destination rule then needs a per-destination grant vocabulary, and the
   measurement of "does the grant match the destination" has to be run
   against the real configuration.
3. A licence or publisher terms question arises that changes what "training
   reuse" may mean for a particular corpus. D1's `train_reuse` grant kind
   may need to be split by purpose.
4. The owner rules that the pilot may proceed on a controlled machine with
   invited annotators. Then D6 stands as written, and the conditions in
   `docs/plans/` become the gate's acceptance list rather than a later
   work order.
