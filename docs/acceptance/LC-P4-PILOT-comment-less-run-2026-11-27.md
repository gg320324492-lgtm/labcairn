# LC-P4-PILOT — the comment-less run

**Ticket:** LC-P4-PILOT (a document with no comments takes part in the model's
role chain)
**Date:** 2026-11-27.
**Tree:** based on `main` @ `92304697d8716caae1f15699f961dae8de5e7ef9` ("Begin the comment-less run: the event,
the chain's shape, role A's abstention"), worktree
`nostalgic-torvalds-90b661`, Windows 11 Pro (10.0.26300 x64), Python 3.12.13.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Command:** `labcairn --workspace <ws> roles run --role <role> --project
<project id> --issue-key <key> [--approval <id>] [--json]`.

**What is claimed here.** The mentor loop's refusal —
`role_comment_not_in_the_chain`, *"the chain holds no comment under the key
…"* — was the only route the CLI had to a model, and it refused every
document the advisor had not written in. The pilot's first round
([`LC-P4-PILOT-first-round-2026-11-26.md`](LC-P4-PILOT-first-round-2026-11-26.md)
§4.1) recorded the gap as *"the suggestion loop — the copy has no
comments"*, and the CLI's own request
([`LC-P4-PILOT-cli-suggest-2026-11-27.md`](LC-P4-PILOT-cli-suggest-2026-11-27.md))
answered one question about one source — **but the chain over a document that
has no comments still did not**.

**This record says what the comment-less run does, what was measured about
it, and what was not exercised.** The run over a document that carries no
advisor's comment now **takes part in the chain**: each role abstains
through its own primitive, the run says what each role could not answer,
the log records the abstention, and **nothing is spent** — no model call, no
approval asked for, no exchange.

**What is not claimed.** That a real model was asked — **it was not, and it
could not have been**: the comment-less run reaches no wire by construction,
so the witnesses use no transport at all. The refusal for a request about a
comment the chain does not hold **still stands, unchanged**, and has its own
witnesses. The chain's own promise — *"a manuscript that holds hundreds of
changes and no comment at all is a shape the chain can report and does not
explain away"* — is the ground this was built on; §2 says why that decided
the shape of the change.

---

## 1. The two cases, and how they are told apart

**The refusal had one reason for two different situations.** A request names
an issue key, and the chain may hold no comment under it for two quite
different reasons:

| the chain holds | what it is | what the loop does |
| --- | --- | --- |
| **no comment at all** | a **shape of the material** — the advisor wrote nothing in the margins of this document | **the run proceeds, and each role says what it could not answer** |
| **comments, but not under this key** | a **mistake about a comment** — the caller asked about a mark that is not the one they meant | **refused by name**, exactly as it always was |

**The branch is taken on the chain's state, not on the request's shape.**
`chain.read_document_shape` reads how many comments the chain holds for the
project; `comment_count == 0` is the comment-less case, and anything else is
the old one. So the two are told apart by a **fact about the chain**, which
a reader can check afterwards, and not by a flag the caller sets — a caller
cannot talk the loop into treating a mistake as a shape.

**And the old refusal is untouched.** `_the_chain` raises
`ApplicationRefusal.ROLE_COMMENT_NOT_IN_THE_CHAIN` exactly where it did,
when the chain holds comments and not one under the key. The witnesses for
it (`tests/test_roles_run.py::test_a_comment_the_chain_does_not_hold_is_refused`,
`tests/test_task_stage_closure.py`) are green and were not weakened.

**What made the choice.** Three of the product's own words:

- `application/chain.py`'s module docstring: *"a manuscript that holds
  hundreds of changes and no comment at all is a shape the chain can report
  and does not explain away"* — **the shape was always meant to be
  reportable**; the refusal was answering a question the chain had not been
  asked;
- `roles/guidance.py::abstaining_card`'s docstring: *"an abstention is a
  result"* — the project already has a shape for "this role could not
  answer", and **the loop was refusing instead of using it**;
- `roles/critique.py`: *"C's honest answer to evidence it cannot reach is
  `cannot_assess`"* — the closed vocabulary already holds the verdict a
  review gives when there is nothing to review.

**The request's shape did not have to change.** The gap's other half — *the
user asked about an issue that has no comment* — is answered by the state,
not by a new field on the request. **The two situations are distinguished by
what the chain holds, and the refusal remains a refusal in both.**

---

## 2. What a role contributes without a comment

**The first question the work order asked: what does a role contribute when
there is no comment to read?** The answer this took is the second of the two
the work order offered, **and it is visible, not a silent skip**:

> the role has nothing to contribute, and **the chain says so**.

**Each role abstains through its own primitive** — not through a shape the
loop invented for the occasion:

| role | what it produces | what it says |
| --- | --- | --- |
| **A** `trajectory` | `TrajectoryAbstention` — **a separate type, and the separation is the point** | *"the chain holds no comment for this document"*, and a note saying why |
| **B** `guidance` | the card the role already produces when it cannot answer: `abstaining_card(issue_type="unknown", …)` | the uncertainty names *"the advisor's remark about this document"* as what is uncertain, and what is missing |
| **C** `critique` | `review_card(…, verdict="cannot_assess", …)` | the repair advice names what was missing, and the handover reason says a person has to act |

**A role that abstained is a role that ran.** The result carries an
`abstentions` mapping — for each role that ran, what that role could not
answer — so **a run that quietly did less than it reported is not possible
through this shape**: the roles are in `roles`, and the abstentions are in
`abstentions`, and a reader of either can see what happened.

**And each role's abstention is carried the way its judgement would have
been.** Role A's is the `TrajectoryAbstention` on the result's `abstention`
field, role B's is the card on `card`, and role C's is the verdict on
`verdict`. **A role that abstained is not a role that returned nothing**, so
its output is a first-class field and not a string in a map.

**Why role A's abstention is its own type.** A `TrajectoryCandidate` carries
`advisor_quote`, and the role checks it **verbatim** against the comment the
chain holds. A candidate with an empty quote would be a shape in which a role
could say *"I judged the advisor's comment"* while having quoted nothing, and
the loop would hand that shape to a reader as a judgement. **So the abstention
carries no quote at all**, and `abstain_from_candidate` refuses an
abstention that names no missing thing (`ABSTENTION_WITHOUT_A_MISSING`) —
because the difference between *"the chain holds no comment"* and *"the
memory holds no rule"* is the difference between a product and an outage.

**The chain's own answer is the document's shape.** The result carries
`ChainDocumentShape` — the project's id, its versions in the accepted
edges' order, how many tracked changes it holds, and **how many comments it
holds**. A count and not an absence: **a chain that holds none says so, as
zero.** The material's text never travels in it.

**And the comment count is the project's, not one version's.** The chain
reads a comment by key, and a key names a comment wherever it was written —
so the count and that read have to agree about the same fact. A count
narrowed to the versions the request named would say *"no comment"* about a
project that holds one, while the read under the same key found it.

**The command answers too.** The gap was found at the command line, so the
command is what has to answer now: `labcairn roles run --json` over a
comment-less document returns the run — the roles, the abstentions and the
shape — and not a pending approval, because there is no call to consent to.

---

## 3. The consent gate still runs first

**The gate-before-the-spend property was not weakened — it was not reached.**
A comment-less run has no judgement to ask the model for, so:

- **no approval is asked for.** `request_role_run` mints an approval only
  when a judgement is missing *and* the chain holds a comment. A run over a
  document with no comment asks no one's consent about a call it will never
  make;
- **no approval is consumed**, because there is none to consume;
- **no wire is reached**, so the transmit gate — which runs first of the
  two, and refuses a call for want of a material-purpose grant — is never
  reached either. **There is no way around the gate here, because there is no
  spend to get around it with**;
- **no exchange is written**, and the log holds no `model_exchanged` event.

**The gate order itself was not touched.** The comment-less branch sits in
`run_role_run`, *before* the call to `request_model` — the one path that may
spend a model call — so the shared path's witnesses stand unchanged and the
new case is inherited by them.

---

## 4. The record

**The events say what happened.** A new event type,
`role_abstention_recorded`, is in the closed vocabulary (**34 types now**),
and its payload names:

- `project_id` — the project whose chain was read;
- `roles` — the roles the request named, in the order they ran;
- `missing` — what each role lacked, keyed by role id.

**Ids and counts, never the material's text** — the log's own currency.

**And the event is an annotation, not an attempt.** It carries **no run and
no operation**: no model was called, no approval was spent, and there is no
attempt for it to belong to. An event that carried a run would be the trace
that could be mistaken for work that was attempted. The three constraints
that say so are in the migration with the type.

**A reader can tell a comment-less run from a commented one afterwards:**

| | comment-less run | commented run |
| --- | --- | --- |
| the log holds a `role_abstention_recorded` | **yes**, naming the project, the roles and what each lacked | **no** |
| the log holds a `model_exchanged` | no | when a model was asked |
| the result's `shape.comment_count` | **0** | the count of the comments held |
| the result's `abstentions` | one entry per role that ran | empty |

**And the run state is closed beside the record.** `record_role_abstention`
writes the annotation and closes the run and its stage **in the same
transaction**, so a reader never sees a finished run without the record of
what it did, nor a record of an abstention inside a run that claims to be
going. The pilot measured that gap: a run that did its work and stopped
left its stage `blocked` and its run `running` although nothing was
waiting.

---

## 5. What was measured

**The witness file:** `tests/test_role_run_commentless.py` — **18 witnesses**.
**They are witnessed by mutation**, which is the only way a witness is known
to watch its property. Four mutations were applied to the implementation, one
at a time, and the tree was run after each:

| mutation | what it breaks | witnesses that turned red |
| --- | --- | --- |
| the comment-less branch returns an empty result — **a silent skip** | the run reports nothing about what the roles could not answer | **8** |
| the abstention event is never written — **the record is dropped** | the log does not say the loop ran | **3** |
| the comment-less case is swallowed by the old refusal | the document is a dead end again | **11** |
| the comment-less run asks for an approval | the gate is reached for a call that will not be made | **2** |
| the comment count is narrowed to the versions named — **the count and the read disagree** | a project that holds a comment is reported as holding none | **1** |
| the comment-less branch refuses again — **the gap comes back** | the document is a dead end at the command line | **11** |

**The last mutation found a real defect, and it is fixed.** The shape's
`comment_count` was first counted over the versions the request named, while
`read_comments` — which every caller in the codebase uses to find a comment
by key — answers for the **whole project**. So a request that named only the
second round of a two-round project would have been told *"this chain holds
no comment"* about a project that holds one, **while the read under the same
key found the comment**. The count and the read have to agree about the same
fact, so the count is the project's count; the versions narrow the shape's
*revisions* and its *order*, and they do not narrow its comments. The
witness is `test_the_comment_count_is_the_projects_and_not_one_versions`.

**The last mutation is the one that matters most for the gate**: it is a
mutation of the *consent* path, and two witnesses turned red —
`test_a_comment_less_run_spends_nothing` and
`test_a_comment_less_run_asks_no_approval_and_the_ask_writes_no_exchange`.

**Two helper defects were found by the new event type and fixed** — both in
the *test* helpers, and both the same class of defect the helpers were
written to prevent:

- `tests/test_runtime_contracts.py::_a_value_for` knew `list` but not `tuple`
  or `Mapping`, so it put `None` into the new payload's fields;
- `tests/test_store_events.py::_minimal_payload` had the same gap, and then
  put a mapping into a `tuple[str, ...]` field.

**Each helper's own docstring says the property it was written to hold** —
*"every kind of field, not only the scalar ones"*, *"the refusal would look
like a defect in the event rather than in the builder"* — and the new event
type is what proved the gap. **The fixes are in the helpers**, because the
helpers are where the property lives.

**The suites that were run, and what they said:**

| suite | result |
| --- | --- |
| `tests/test_role_run_commentless.py` | **18 passed** |
| `tests/test_roles_run.py` | green (the old refusal's own witnesses) |
| `tests/test_role_run_entry.py` | **30 passed** (the API's two routes and the CLI's one command) |
| `tests/test_runtime_contracts.py` | **83 passed** |
| `tests/test_store_events.py` | **122 passed** (the vocabulary's sweep, 34 types) |
| `tests/test_store_migrations.py` | green (revision 0035 and the downgrade) |
| `tests/test_task_stage_closure.py` | **4 passed** (the refusal's own log witness) |
| the thirteen suites above, together with `test_api.py`, `test_cli.py`, `test_application_layer.py` and the four role suites | **486 passed, 1 skipped** |
| `ruff check .` / `ruff format --check .` | **all checks passed** |
| `mypy --strict src/ tests/` | **success: no issues found in 506 source files** |

**The environment, and one measurement that was lost and re-taken.** The
twelve `tests/test_role_run_entry.py` failures seen earlier were
**environmental, not behavioural**: the console script `labcairn.exe` was not
on the interpreter's path. With `E:/LabCairn/.venv` (which holds the console
script) and the worktree's own `src` first on `PYTHONPATH`, the suite is
**30 passed** — and it is 30 passed *with the change in the tree*, which is
the number that matters.

**What was not measured here.** The whole suite was not run in this window:
the tree carries changes from three other windows, and the suites that touch
the CLI's packaging, the PDF path and the developer launch fail for reasons
that are in the environment rather than in this change — a missing
`pdfplumber`, a console script that is not installed for the interpreter that
runs the suite. **A migration A/B was run to settle the question for the
migration alone**: moving `0035_role_abstention_event.py` out of the tree and
back again changed **no** test's outcome.

---

## 6. The files

| file | what changed |
| --- | --- |
| `src/labcairn/application/roles_run.py` | the comment-less branch, the abstaining run, the wire's `abstentions` and `shape` |
| `src/labcairn/application/chain.py` | `read_document_shape` — the document's own shape, and the count of the comments held |
| `src/labcairn/application/records.py` | `record_role_abstention` — the annotation, and the run and stage closed beside it |
| `src/labcairn/roles/trajectory.py` | `abstain_from_candidate` — role A's abstention, and its own type |
| `src/labcairn/runtime/event.py` | the `role_abstention_recorded` type and its payload |
| `migrations/versions/0035_role_abstention_event.py` | the table rebuild, with the vocabulary the models now carry |
| `src/labcairn/cli/commands.py` | the renderer shows the abstentions and the shape |
| `web/src/api/generated.ts` | regenerated from the OpenAPI document |
| `tests/test_role_run_commentless.py` | the 18 witnesses |
| `tests/test_runtime_contracts.py`, `tests/test_store_events.py` | the two payload builders, which knew `list` but not `tuple` |

---

## 7. What is still open

- **`tests/test_ci_shard_coverage.py` is red on this branch, and it should
  be.** The new test file is in no shard, and the integrating session
  registers it in the manifest and in a shard after the batch merges. **The
  file being in no shard means CI never runs it** — that is the thing to fix
  first, and it is not this window's to fix.
- **The pilot's own material was not touched.** No request was made to any
  model, and nothing under the pilot workspace or the owner's corpus was
  read. What is measured here is the product's behaviour on the project's
  own fixtures.
- **A run over a document with no comment and a rule the card would cite was
  not exercised by this window** — the comment-less run has no card to cite a
  rule from. **Correction, 2026-11-27: the rule *is* fetched, and this record
  said otherwise.** It said *"the rule the request names is not fetched"*, and
  the measurement says the opposite: `the_role_run_question` calls
  `_the_rule(context, request)` — which is `cite_rule`, which **raises**
  `RULE_NOT_IN_THE_MEMORY` when the memory holds no rule under that id —
  and the question is built **before** `_run_role_run` reaches its
  comment-less branch. So **naming a rule the memory does not hold refuses
  the whole request**, with `RULE_NOT_IN_THE_MEMORY`, before the chain's
  "no comment" state is ever consulted: a document with no comments that
  names a rule the memory lacks is **refused, not abstained**.
  **Answered 2026-11-27.** The next window measured both directions and the
  product's answer is the code's. A rule the memory does not hold refuses the
  request by name, at the ask step, before any consent is minted; a rule the
  memory serves does not stop the comment-less answer — the run abstains,
  spends nothing, the ticket's question carries the citation, and the result's
  abstaining card cites no rule. What made that the answer, and what a
  document naming a rule the memory serves answers, is in
  [`LC-P4-PILOT-comment-less-and-a-rule-2026-11-27.md`](LC-P4-PILOT-comment-less-and-a-rule-2026-11-27.md);
  the witnesses are `tests/test_role_run_commentless_rule.py`.
- **What the count's narrowed scope would have answered was not measured
  here.** The change from a version's count to the project's is asserted, not
  compared. A later window measured it: the old count answers *no comment* in
  two shapes where the project holds one — see the same record.
