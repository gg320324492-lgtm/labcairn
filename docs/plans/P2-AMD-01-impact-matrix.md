# P2-AMD-01 — The impact matrix: what the route change touches, and what it does not

**Status:** the first deliverable of the incremental adjustment P2-AMD-01
(2026-10-30). **It is a matrix, not a new plan.** Every work order keeps
its number; nothing here reopens an accepted module.

**What was read to produce it:** the current `main` at **`179f386`** — which
is **two commits past** the `503b5fe` P2-AMD-01 names, because LC-P2-06's
review fixes and LC-P2-09's design landed in between. The tree that this
matrix describes is therefore **newer** than the one the adjustment was
written against, and every row below was checked against it.

**The principle the adjustment states, and this matrix keeps:** *align,
do not roll back*. A row that says "keep" means the work is already done
and its tests still hold; a row that says "supplement" means the work
order's **contract** is extended, not replaced.

---

## 1. The matrix

| Work order | Disposition | What changes, and in what | Risk |
|---|---|---|---|
| **LC-P2-00** Freeze the P1 baseline | **keep** | Nothing. It is still the denominator the exit gate needs, and the adjustment does not change the gate. | Low. **But note:** the baseline must be frozen *before* the cloud-model path exists, or the "before" arm has no model in it at all. |
| **LC-P2-01** The model-call path | **supplement** | The path becomes **configurable across cloud providers**, and it takes the **two independent gates** from LC-P2-06: the operation approval (LC-P2-02) and the material-purpose grant. **No second, parallel API path** — one provider boundary. A model id, an endpoint, a price or a capability is **never written into the tree**: the provider is configuration, and each supplier's connectivity and structured-output behaviour is measured separately. | **Both gates are connected as of 2026-10-31.** `external_transmit` was correct and unwired; the pilot's first real request (2026-10-31) went through the material-purpose grant *and* the operation approval, and the approval was consumed exactly once. **What is still unwired is the writer:** nothing in `src/` writes a grant row, so the pilot's grant was written by a script outside the product. |
| **LC-P2-02** Restart-durable consent | **keep, and go first** | Unchanged in content; **its priority rises**, because it is the operation half of LC-P2-01's gate and the adjustment's second step names it. | Low. Its own debt — the approval row holds no grant-time policy digest and no bound-source column — is untouched by the adjustment. |
| **LC-P2-03** The competitor baseline | **keep** | Unchanged. The adjustment adds a requirement the draft already implies: the comparison must be **like-for-like on the same tasks and a comparable budget**, and **a difference in role is not a weight-training result**. | Low. But a comparison against a **cloud** model needs the budget and the model version recorded; Phase 1's baseline mechanism already records the model name. |
| **LC-P2-04** Citation identity and support | **keep** | Unchanged. | Low. |
| **LC-P2-05** Retrieval beyond three papers | **keep** | Unchanged, and it becomes **the retrieval half of LC-P2-11**: the guidance memory is a *retrieval over stored cases and rules*, not a second database. The adjustment says so explicitly: *"do not introduce a second database without permissions for 'memory'"*. | Low. **One boundary to hold:** the memory retrieval is a **different query** from a literature retrieval, and it must not be able to reach material the consent does not cover. |
| **LC-P2-06** Data governance, consent and access | **keep the implementation; supplement the wiring** | The grant table, the permission check, the two gates, the withdrawal and the intake guards **are done and measured** (`503b5fe`; the record is `docs/acceptance/LC-P2-06-acceptance.md`). What is missing is **wiring**: nothing in `src/` reads a grant row, and **the withdrawal's propagation has no production caller**. The adjustment asks for exactly this: *"check the wiring, do not redo it"*. | **Medium.** A gate that nothing calls is a gate that cannot be exercised. The acceptance clause the adjustment names — *"the withdrawal's indexes and caches really stop"* — needs a caller, and that caller is LC-P2-01's model path. |
| **LC-P2-07** DOCX revision and comment fidelity | **keep the implementation; supplement the reading** | The reader, the two views, the anchors and the fidelity numbers are **done and measured**. Two additions, both small and both in this repository's existing shape: the **anchored text** is not carried today (`CommentAnchor.text` is `""` on every path), and the **events are not persisted** into the version graph. | **Medium.** An anchor with no text is an address to nothing, and LC-P2-09's first link is that text. |
| **LC-P2-08** Paper projects and the version graph | **keep the contracts; supplement the writer** | The tables, the models, the alignment, the confirmation path and the duplicate/gap checks are **done and measured**. **There is no writer**: nothing in `src/` stores a `PaperVersion` or a `VersionEdge` — `confirm_edge` builds in-memory edges and `propose_alignment` builds a proposal. The adjustment's *"add the seam from revision events to persistent versions and feedback relations"* is exactly this. | **Medium.** Everything downstream names an edge. **This is being done inside LC-P2-09 as its first subtask (T00),** because LC-P2-09's edit rows name an edge and an edge that cannot exist is a reference to nothing. |
| **LC-P2-09** Feedback, response and follow-up | **keep the design; supplement the contract** | **Designed on 2026-10-30** (`ADR-0017`, `LC-P2-09-task-breakdown.md`) and **under implementation now**. The adjustment's requirement — *"support candidates, unknowns and human confirmation"* — is **already the design's shape**: the three evidence grades, the nullable `issue_key`, and the judgement-with-evidence. One thing the adjustment sharpens, and it is a **real gap in ADR-0017**: see §2.2. | **Low** — the design is young enough to take the correction now. |
| **LC-P2-10** Process annotation and the gold set | **supplement** | The label guide and the gold set stay; the annotation **must be able to label a candidate as a candidate** and **`UNKNOWN` as a label** — both are already the design's vocabulary. | Low. The split by `PaperProject` is unaffected. |
| **LC-P2-11** The mentor guidance memory | **rewrite the route, keep the contract** | The **contract does not change** — a rule has a source anchor, a scope, a counterexample, a version and a withdrawal state, and a withdrawn source invalidates the rule. **The route does**: it becomes **retrieval over stored cases and rules**, not model parameters, and **LoRA/DPO move to LC-P2-15's optional research**. | **Medium.** The dangerous version of this work order is *"store the advisor's style in weights"*, and the adjustment exists to stop it. |
| **LC-P2-12** The guided-revision agent | **rewrite the implementation, keep the prohibitions** | This is where the three roles live: **A** extracts trajectory candidates, **B** produces a `GuidanceCard`, **C** reviews it independently. The prohibitions are unchanged and already written: no invented experiment, no invented citation, no invented advisor's opinion, **no writing back to the manuscript**, and no automatic promotion of a proposal. | **Medium.** "Another agent agrees" is not evidence, and the adjustment says so twice. The card's `uncertainty` and `counterexamples_or_limits` are fields, not caveats. |
| **LC-P2-13** The peer-review loop | **keep; connect to the same event chain** | `ReviewerComment → AuthorResponse → RevisionEvidence → NextReview` joins the same chain LC-P2-09 builds, so the review outcome is **retrievable evidence** for LC-P2-11's rules. The prohibition is unchanged: **a response claiming an experiment the manuscript does not contain is not marked done.** | Low. |
| **LC-P2-14** Blind evaluation and ablation | **supplement** | The five arms stay. **One independent variable is added**: the same evidence and the same underlying model, comparing **`B-only` against `B+C`**, with cost and latency recorded. And **"not significant" stays a reportable result.** | **Medium.** The danger here is reporting the multi-agent result as a win because there are more agents. The adjustment forbids that in the same words. |
| **LC-P2-16** The workbench for the guidance line | **new, and it is the interface of the whole adjustment** | The adjustment's promise is that the system learns from a paper's revision history and proposes guidance on a new one — and **the workbench has not moved at all**: `web/package.json` still says "Phase 1 baseline skeleton, no product features yet", and the only change under `web/` in the Phase 2 range is a regenerated TypeScript contract. The plan is [`LC-P2-16-task-breakdown.md`](LC-P2-16-task-breakdown.md): the contract's outlets first and the views second (the workbench's own rule is that a view draws only what the contract carries), the rules' confirmation door, and the loop on demand — a gated two-step action, never a button that quietly spends. **The desktop shell is deliberately not here**: packaging and multi-platform distribution are Phase 3's row, and the owner ruled on 2026-10-31 that the interface comes first. | Medium. A capability nobody can see is a capability nobody can believe — but the shell is not what makes it visible. |
| **LC-P2-15** Strategy optimisation | **defer, and say so** | LoRA, DPO, a specialised small model and prompt/strategy optimisation become **optional research, decided by data volume, permission and measured blind-review gain**. **They are not a Phase 2 exit requirement.** | Low. |

## 2. The conflicts, and what they cost

**The adjustment says to list conflicts rather than overwrite silently.** These
are the ones that exist.

### 2.1 LC-P2-06's gates are correct and unwired

**The state.** `access_grants`, `derived_copies`, the permission check, the
two gates and the refusal vocabulary are done and measured. **But nothing in
`src/` reads a grant row**: `may_use` is called from `model_transmit.py`
alone, `inspect_archive` from nothing, and `stale_copies` from nothing.
**The withdrawal's propagation is therefore checkable and not wired** — the
adjustment's question ("is the withdrawal's propagation to indexes and
caches really wired?") answers **no**, and the answer is about *wiring*, not
about the mechanism.

**Updated 2026-10-31 — the transmit gate is now wired, and the gap that
remains is the writer.** `may_use` was already called from
`model_transmit.py`, and the pilot's first real request exercised it: the
material-purpose grant was read, judged and **refused twice** — once because
the grant's scope did not reach the material, once because the approval's
task scope did not match — each refusal naming its remedy, before the
approval was consumed. So "the refusal does not spend the approval" is
now exercised in the product, against a real endpoint.

**What is still unwired is the other side of the table.** Nothing in `src/`
*writes* a grant row, so the pilot's grant was written by a script outside
the product; and `inspect_archive` and `stale_copies` still have no
production caller. **The withdrawal's propagation remains unwired**, which
is the adjustment's own question and still answers **no**.

**What it costs to close it.** LC-P2-01's path has to call the transmit
gate **before** the approval is consumed, and the withdrawal has to reach
whatever indexes the model path builds. Both are in the second step's scope,
and **neither is new** — the pieces exist.

**What it does not cost.** Nothing in LC-P2-06 is redone. The review of
LC-P2-06 (merged as `503b5fe`) found seven gaps and fixed all seven; this
matrix does not reopen them.

### 2.2 ADR-0017 needs one correction, and the adjustment is what found it

**The conflict.** The adjustment's role A *"proposes `FeedbackEvent` /
`EditAction` / `ResponseLink` candidates"*. ADR-0017 §D1 says a feedback
row carries the comment's own locator, and §D4 says an edit row names the
feedback it answers. Read together, they make a **model-proposed feedback
row** look like a comment — and a comment is a **fact about a file**.

**Why it matters.** The prohibition is exact: *"without the original
comment, it may not claim the advisor said something."* A row with a
`comment_locator` that was never read **is** the advisor being claimed to
have said something.

**The correction, and it is small.** The three objects have different
standing, and the adjustment makes it plain:

| | What it is | Who may create it | Grade |
|---|---|---|---|
| `feedback_events` | **a fact about a file** — a comment that is there | **only the reader** | `observed` |
| `edit_actions` | **a fact about the manuscript's history** — a change that is there | **only the reader and the version graph** | `observed` |
| `response_links` | **a judgement** — "this change answered that comment" | **a rule, a person, or a model** | `observed` / `human_verified` / **`inferred`** |

**So a model proposes a judgement, and never a fact.** A model's candidate
is a `response_link` at grade `inferred` — it carries no `comment_locator`,
because it read no comment of its own; it *points at* one. This is ADR-0016's
`model_proposal` rule applied to the chain, and it is the same shape the
evidence ledger already has.

**What it costs.** ADR-0017 §D5 gains a `grade` column and a rule; §D1's
"a row without a version is refused" stays; and the acceptance clauses A6,
A11 and A13 are read as *"a candidate is a candidate"*. **Nothing is
re-implemented.**

### 2.3 The adjustment supersedes one of CLAUDE.md's rules, and says so

CLAUDE.md (the owner's ruling of 2026-10-24) says: *"Do not open a pull
request. Not for a finished piece of work, not for a document, not for a
commit that is 'ready to be reviewed'."* P2-AMD-01 (2026-10-30) says
*"routine development may proceed continuously; it does not need to wait for
my review at each pull request."*

**The later decision governs the working rhythm.** So: work lands on a
branch and a pull request is opened when a body of work is ready, **without
waiting for a per-pull-request review**; and **`main` stays protected**, so
the pull request is still how anything reaches it. **What does not change:**
the sixteen required checks still run on it, and the review that decides
whether a work order is *accepted* is still the independent one.

### 2.4 Three roles do not need three models, and the adjustment is right

The adjustment says one base model may play several roles, and that the
difference between roles is **responsibility, data input, tool permissions,
output contract and failure hand-off** — not a different system prompt. **The
tree agrees:** `CapabilityId` already carries a per-capability argument
model and a root kind, and the provider boundary already carries a budget
and a transcript. **A role is a capability with a contract**, and the
contract is where the difference lives.

### 2.5 The two gates are two gates, and the tree already says so

The adjustment's §4 requires the operation approval **and** the
material-purpose grant, with the material check **first**. ADR-0015 D2/D3
and LC-P2-06 say the same thing, and LC-P2-06's `transmit_request` (merged
in `503b5fe`) implements the order. **No conflict; the wiring is what is
missing** — see §2.1.

## 3. New objects, and where they live

**The numbering rule holds.** No `LC-P2-xx` is reused or renumbered.

| Object | Where | Why there and not elsewhere |
|---|---|---|
| `AgentRoleSpec` | **a new ADR** (the adjustment's §3), and its implementation as **sub-tasks under LC-P2-12**, not a new work order | It is the **contract** of the three roles, and LC-P2-12 is the work order that implements them. A versioned role spec with `role_id`, `role_version`, schemas, capabilities, budgets and abstain/escalate conditions is a **schema and a table**, not a work order. |
| `GuidanceCard` | **LC-P2-12** (already its objective) | Already the work order's own deliverable. |
| `ReviewVerdict` | **LC-P2-12** as role C's output | Role C is part of the same closed loop; giving it its own number would split one work order into two. |
| The route and budget policy | **LC-P2-01's** contract, amended | The provider boundary, the budget and the transcript are already LC-P2-01's. |
| The retrieval over guidance rules | **LC-P2-11**, with **LC-P2-05**'s retrieval machinery reused | The adjustment forbids a second database without permissions. |

**And the numbering rule's exception, stated once:** if the implementation
shows that a role spec needs its **own** work order (because it has its own
acceptance and its own cost), **a free number is requested** — the
adjustment says exactly this, and this matrix does not reserve one.

## 4. What the adjustment changes about the delivery order

**The adjustment's five steps map onto the existing work orders, and the
order is compatible with what has already landed:**

| Step | Work orders | Depends on |
|---|---|---|
| 1. Plan revision and dependency check | **this matrix**, the role ADR, the amendments below | — |
| 2. The trusted cloud-model path | **LC-P2-02**, then **LC-P2-01**, wired to **LC-P2-06**'s transmit gate | LC-P2-02's durable approval; LC-P2-06's grant table (**done**) |
| 3. Trajectory to retrievable experience | **LC-P2-07** (done) → **LC-P2-08** (contracts done, writer missing) → **LC-P2-09** (in progress) → **LC-P2-10** → **LC-P2-11** | LC-P2-08's writer, which is **LC-P2-09's T00** |
| 4. The three-role loop | **LC-P2-12** with **LC-P2-13** | LC-P2-09's chain, LC-P2-11's rules |
| 5. Evaluation and decision | **LC-P2-14**, with **LC-P2-03** | everything above, and **LC-P2-00's frozen baseline** |

**And LC-P2-15 leaves the critical path entirely.**

**Where the five steps stand on 2026-10-31.** Steps 2, 3 and 4 have
**landed**: the cloud-model path (LC-P2-02, LC-P2-01, wired to LC-P2-06's
transmit gate — and the first real request went through it), the chain from
the reader to the version graph and the retrievable experience (LC-P2-07,
LC-P2-08, LC-P2-09, LC-P2-10, LC-P2-11), and the three-role loop
(LC-P2-12). **The pilot's first real request on the owner's own paper is
the first exercise of steps 2–4 together**, and the reading exercise ran
over the owner's real advisor comments.

**So the remaining work is step 5 and the wiring the pilot exposed**, and
the pilot's own book names them: the **store-boundary repair** (seven
domain modules reach past the application layer to the store), the
**grant writer** (nothing in `src/` writes a grant row), the **record
advance** (the machinery that would let a person confirm a model's
proposal has no door), the **probe record's persistence**, and a **CLI for
the model path**. LC-P2-14's evaluation and LC-P2-03's baseline are what
remain of step 5, and LC-P2-00's frozen baseline is still its
denominator.

## 5. What the owner must decide

**The adjustment names four.** They are carried here unchanged, with what
each one blocks:

1. **Which suppliers and which data categories are permitted.** It blocks
   LC-P2-01's provider configuration and any real (non-`FakeProvider`) smoke.
   **Ruled in substance on 2026-10-31:** the owner's own MiniMax endpoint
   is the pilot's supplier, the credential is the owner's, and the pilot's
   first real request went through it against the owner's endpoint. **The
   general rule — which suppliers may be configured for other work — is
   still open**, and the answer is a configuration question, not a code one.
2. **The per-task budget and the total budget.** It blocks LC-P2-01's
   budget policy and LC-P2-02's consumption semantics. **Ruled 2026-10-30:
   zero until a number is given** — a real call is refused, and the offline
   path runs the scripted provider. **Supplemented 2026-10-31, for the
   pilot's first request only:** the owner set **one request and four
   thousand tokens, and no money ceiling** — MiniMax has no price table, so
   a money ceiling nobody can measure fails closed and would have refused
   the request. The zero rule still stands for everything else.
3. **The authorisation for the pilot's first batch of material.** It blocks
   any real transmit and the pilot's corpus. **Ruled 2026-10-31:** the
   owner's material is in the library, and the first real request carried
   **507 characters** of it — the advisor's comment, the passage it is
   anchored to and the paragraph it sits in — named in the approval's
   arguments, so the approval's digest binds that excerpt and not another.
   The first request before it carried **nothing**: it asked the model to
   judge a manuscript without being given one, and the model said so.
4. **The scope of a multi-person deployment.** It blocks ADR-0015 D6's
   identity model, and therefore any claim that the chain is safe beyond
   the administrator. **Still open.**

**Two more this matrix found, and both are cheap to decide now:**

5. **May a candidate response link carry a `comment_locator`?** The
   recommendation is **no** — a candidate points at a comment, it does not
   claim to be one (§2.2). **If the answer is yes, ADR-0017 §D1 changes and
   the prohibition in the adjustment's role A becomes unenforceable.**
   **Ruled 2026-10-30: no** — the answer the recommendation gave.
6. **Does LC-P2-09's T00 (the version graph's writer) stay inside LC-P2-09,
   or become LC-P2-08's own ticket?** The recommendation is **inside
   LC-P2-09** — the owner has already ruled that way for this round — but
   the alternative is defensible, and it changes which acceptance record
   carries the clause. **Ruled and landed: inside LC-P2-09**, and PR #130
   carries it.

## 6. What this matrix does not do

- **It does not re-open anything accepted.** LC-P2-06, LC-P2-07 and
  LC-P2-08's records stand, and their tests still pass on this tree.
- **It does not invent work.** Every row names work that already exists in
  the plan; the matrix says what changes about it.
- **It does not claim the phase can show a gain.** That is LC-P2-14's job,
  on a frozen baseline, with a blind annotator who did not build the system.
- **It does not decide the supplier, the budget, the pilot's authorisation
  or the deployment scope.** Those are §5, and they are the owner's.
