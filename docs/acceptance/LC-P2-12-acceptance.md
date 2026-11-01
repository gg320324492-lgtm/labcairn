# LC-P2-12 — The three-role guidance loop — acceptance

**Work order:** LC-P2-12 (the guided-revision agent) · **Subtasks:**
T00–T05 · **Task breakdown:**
[`../plans/LC-P2-12-task-breakdown.md`](../plans/LC-P2-12-task-breakdown.md) ·
**Status of the work order:** **implemented and measured**, and **independently reviewed** — the review's weakest point is
named at the end of this record. The role contract, the three roles, the
arrangement, the demonstration and this record are landed.

**What this is.** The guidance loop as three roles — A proposes the
revision trajectory, B writes the card, C critiques it independently —
each working under **a contract that is a row, not a prompt**: the
capabilities it may exercise, the five actions it may not take, the
purposes it may read for, its budgets, and the conditions under which it
abstains or hands the work to a person. Around them, the arrangement
that decides which roles run **from a table**, the budget that fails
closed when its price is unknown, and the ledger that records a
person's decision.

**What this is not.** It is not three good advisors. The work order §5
says so in its own words: this makes the loop **consented, budgeted,
recorded, refusable and abstaining**; whether the advice helps is
LC-P2-14's question. And it does not send anything — the demonstration
runs on `FakeProvider`, and **a real run is the owner's
authorisation**, which has not been asked for.

---

## 1. The decisions, and where each is held

| # | The decision | Held by | Witnessed by |
|---|---|---|---|
| 1 | **A role's contract is a versioned row, and the code enforces it** — `require_allowed` for a capability, `refuse_forbidden` for an action, each refusal machine-readable; the version rides on every output through `RoleOutput` | `src/labcairn/roles/models.py` (the contract and its enforcement), `src/labcairn/roles/spec.py`, the `agent_role_specs` CHECKs | `test_a_role_spec_is_versioned_and_the_version_is_on_the_output`, `test_a_call_outside_the_role_spec_is_refused`, and the schema refusals by raw `INSERT` |
| 2 | **The five forbidden actions are closed** — a sixth arrives by editing `ForbiddenAction`, not by typing it into a spec; and the module's import surface is watched, so a role holds no socket and no requests | `ForbiddenAction`, `test_a_role_holds_no_direct_path_out`'s AST check | `test_a_role_holds_no_direct_path_out`, `test_an_unknown_capability_or_action_is_refused_by_name` |
| 3 | **A candidate is a judgement, never a fact**: `TrajectoryCandidate` has no `comment_locator` field — the shape itself refuses — and the advisor's words must sit verbatim on the chain | `src/labcairn/roles/trajectory.py` | `test_role_a_proposes_judgements_and_never_facts` |
| 4 | **The version order is walked, not spelled**: only accepted edges, Kahn's order; a version outside the graph and a fork are refused rather than ordered by file name | `order_versions` | `test_role_a_does_not_order_versions_by_name_or_invent_a_round` |
| 5 | **An abstention is a result**: kind `abstention`, and the missing named — an abstention that names nothing is refused | `abstaining_card` | `test_insufficient_material_produces_a_named_abstention` |
| 6 | **A rule is cited with its counter-examples, and they cannot be trimmed** — the citation carries the rule's cases against itself, because a rule without its failure cases is an advertisement | `cite_rule` | `test_a_card_cites_a_rule_with_its_counterexamples` |
| 7 | **A verdict enters the ledger at the grade its evidence supports** — every review verdict is `inferred`, and the review writes no store row at all (counted, not asserted); the counter-evidence is **C's own retrieval**, not a field B filled in | `REVIEW_GRADE`, `review_card`, `search_rules` | `test_a_verdict_does_not_promote_a_proposal`, `test_role_c_reads_the_sources_and_its_own_counterevidence` |
| 8 | **The routing is data**: the tables are parameters, the kind vocabulary is closed (there is no swarm), and every role runs for a recorded reason; a cost ceiling that is not priced refuses, and a retry is the same plan | `ROUTING_TABLE`, `ESCALATION_TABLE`, `prepare_invocation`, `retry` | `test_the_roles_that_run_are_the_ones_the_request_needed`, `test_an_unmeasurable_cost_refuses_and_a_retry_does_not_pay_twice` |
| 9 | **A person decides, and the decision is audited**: the ledger appends and cannot edit — a change of mind is a second record | `DecisionLedger`, `record_human_decision` | `test_a_human_decision_on_a_card_is_audited` |
| 10 | **A card carries an address of its own** — the owner's decision of 2026-11-01: the address names the comment the card is about (the chain's issue key, the comment's row, the version the comment was written against), it is **minted by the product** from the card's own evidence, and **a caller may not supply it** — the shape refuses before the body runs | `CardAddress`, `the_card_address`, `build_card` | `test_a_card_carries_an_address_of_its_own_and_a_caller_cannot_supply_it`, `test_a_recurring_issue_is_addressed_by_the_comment_the_card_quotes` |
| 11 | **And the review checks that address, and not the card's word about it**: the review mints the address again from the same evidence and compares, so a card whose address names a comment the chain does not hold is refused by name — and the refusal does not wait for the verdict | `_check_the_card_address` | `test_the_review_checks_the_card_address_and_not_its_word` |

**And where the rows are reached.** The contract's table and the chain's own
facts are read and written through the application layer —
`src/labcairn/application/roles.py` for the contracts,
`src/labcairn/application/chain.py` for the comments, the changes, the
judgements and the accepted edges — so the mentor line is reached in one place
and a guard applied there reaches every caller. **The contract itself is data**
in `src/labcairn/roles/models.py`, below both, because the layer answers with a
contract and the contract's own lifecycle calls the layer.

## 2. What the schema refuses, and how that is witnessed

`agent_role_specs`' CHECKs are witnessed the way revision 0007 taught:
**by writing the rows the schema must refuse** — eleven raw `INSERT`s in
`test_the_schema_refuses_what_the_api_refuses`, each bypassing the ORM:
the empty texts, the version below one, the zero ceilings, the columns
that are not JSON arrays, the list that is empty where the contract
cannot be empty. A constraint nobody has violated is a comment.

## 3. The work order's acceptance clauses, and where each is carried

| # | The clause | The test | State |
|---|---|---|---|
| A1 | a role's contract is versioned, and the version is on every output it produces | `test_a_role_spec_is_versioned_and_the_version_is_on_the_output` | landed |
| A2 | a role may exercise only the capabilities its contract lists, refused with a machine-readable reason | `test_a_call_outside_the_role_spec_is_refused` | landed |
| A3 | a role holds no database connection, no arbitrary file-write permission and no direct network path | `test_a_role_holds_no_direct_path_out` | landed |
| A4 | role A's candidate is a judgement: no `comment_locator`, and no claiming of the advisor's words | `test_role_a_proposes_judgements_and_never_facts` | landed |
| A5 | role A orders versions by the graph, never by file name, and invents no round | `test_role_a_does_not_order_versions_by_name_or_invent_a_round` | landed |
| A6 | a card carries every field, and a card without evidence is refused | `test_a_card_carries_its_fields_and_one_without_evidence_is_refused` | landed |
| A7 | a card cites a rule with its counter-examples | `test_a_card_cites_a_rule_with_its_counterexamples` | landed |
| A8 | insufficient material produces a structured abstention naming what was missing | `test_insufficient_material_produces_a_named_abstention` | landed |
| A9 | a card invents no experiment, no reference and no advisor's opinion | `test_a_card_invents_no_experiment_reference_or_opinion` | landed |
| A10 | scientific facts and stylistic advice are recorded separately | `test_facts_and_style_are_recorded_separately` | landed |
| A11 | role C reads the original material and retrieves its **own** counter-evidence | `test_role_c_reads_the_sources_and_its_own_counterevidence` | landed |
| A12 | a verdict enters the ledger at the grade its evidence supports, and two models agreeing promotes nothing | `test_a_verdict_does_not_promote_a_proposal` | landed |
| A13 | the roles that run are the ones the request needed, and the decision is recorded | `test_the_roles_that_run_are_the_ones_the_request_needed` | landed |
| A14 | an unmeasurable cost refuses, and a retry does not pay twice | `test_an_unmeasurable_cost_refuses_and_a_retry_does_not_pay_twice` | landed |
| A15 | a human may accept or reject a card, and the decision is audited | `test_a_human_decision_on_a_card_is_audited` | landed |
| A16 | no role may write back to the manuscript, release unauthorised material, or execute code | `test_no_role_may_write_back_release_or_execute` | landed |
| A17 | the demo is run by a test, and it sends nothing | `test_the_guidance_loop_demo_runs`, `test_the_demonstrations_exit_code_still_means_something` | landed |

## 3a. The decision of 2026-11-01: a card has its own address

**The problem it answers.** The orchestration's §7.3 wants "the model's
answer enters the ledger as a proposal a person can settle", and
ADR-0016's promotion path wants the proposal to carry a source address.
**But the chain's comments live in the DOCX's `word/comments.xml` part,
and the ledger's extracted text has no address in that part** — the
ledger's own source anchors name the document's *body* paragraphs. So
there was no address in the ledger that a proposal about a chain comment
could point at, and the card's `target_locator` was either a body
paragraph address the ledger could not resolve for a comment, or — as
the loop filled it — the evidence reference's own spelling, `chain:<key>`,
which is not an address at all.

**What the card's address is made of, and what each piece is for.** It
is made of three names the chain holds, and each answers a question of
its own:

| The piece | What it is for |
|---|---|
| the chain's **issue key** | *what* the card is about — and it is the key the card's evidence already carries, so the address and the evidence cannot disagree about the subject |
| the comment's **row** (`feedback_id`) | *which* comment — one issue key can carry several comments, and an address that could be two addresses is not an address |
| the **version** the comment was written against | *which round* — the advice is against a manuscript state, and a later state is a different manuscript |

**Who mints it.** The product, from what the card already holds: the
card's `evidence_refs` name the chain comment, and `build_card` reads
the chain and mints the address. **There is no `target_locator`
parameter to fill in** — the shape refuses a caller that offers one,
before the body runs, the same way `TrajectoryCandidate` has no
`comment_locator` field for role A. When one issue key holds several
comments (a recurrence is a fact about two versions), **the card's own
quoted words say which one it is about**; a card that quotes neither
cannot be addressed, and is refused.

**What it must never be.** Not a source address in the ledger's own
sense: the ledger's anchors name body paragraphs, and a card about a
comment in `comments.xml` is not one. So the address is spelled in its
own namespace (`card:`), and it is **not** the comment's own locator
borrowed and worn — the application layer does not hand that locator
over, because `read_comments` does not carry it.

**What the card's `target_locator` becomes.** It is the card's address,
and nothing else. It no longer says "where in the manuscript this
points" (the card is not a claim about the manuscript) and it is no
longer the evidence reference's spelling. **It says where the advice
came from**, so a person settling the proposal can find the comment
behind it.

**And the loop stopped filling it by hand.** The loop used to pass
`request.target_locator or f"chain:{request.issue_key}"`; the request
has no such field now, and the loop's card carries the address the
product minted. The demonstration was changed with it, for the same
reason: it used to fill the address in by hand, and it now uses the one
the card carries — including as the key the person's decision is
recorded under.

**What the critique verifies, before and after.** Before: the card's
`chain:` evidence references were checked against the chain, a reference
in no form the review could check made a `supported` verdict a lie, and
the review wrote nothing. After: **the same, and the card's address as
well** — the review mints the address again from the card's own
evidence and compares it with the one the card carries. A card whose
address names a comment the chain does not hold, or borrows a place in
the manuscript, is refused by name; **and the refusal does not wait for
the verdict**, because `cannot_assess` is the honest answer to evidence
the review cannot reach, and not the answer to a card that is not what
it says it is.

## 4. The mutations, and what each one proved

| # | The mutation | The witness it reddened |
|---|---|---|
| 1 | the capability gate neutered (`AgentRoleSpec.allows` returning `True` unconditionally) | `test_a_call_outside_the_role_spec_is_refused` — exactly one |
| 2 | the fork refusal neutered (`if len(ready) > 1` no longer raises) | `test_role_a_does_not_order_versions_by_name_or_invent_a_round` — exactly one |
| 3 | the citation's counter-examples discarded (an empty tuple returned in their place) | `test_a_card_cites_a_rule_with_its_counterexamples` — exactly one |
| 4 | the critique's own retrieval discarded (`counter_evidence` built from nothing) | `test_role_c_reads_the_sources_and_its_own_counterevidence` — exactly one |
| 5 | the high-risk escalation neutered (the `high_risk` branch no longer adds the critique) | `test_the_roles_that_run_are_the_ones_the_request_needed` — exactly one |
| 6 | the demonstration's first claim planted false from outside the source, and then the planting itself neutered — the second mutation reddened `test_the_demonstrations_exit_code_still_means_something` alone, which is what proves the first | the exit-code witness — exactly one, both times |
| 7 | **the card's address made supplyable** — a `target_locator` parameter added to `build_card` and used when given | `test_a_card_carries_an_address_of_its_own_and_a_caller_cannot_supply_it` — exactly one |
| 8 | **the card made to borrow the chain's comment locator as its own** — the address built from the comment row's own `comment_locator` instead of the chain's names | `test_a_card_carries_an_address_of_its_own_and_a_caller_cannot_supply_it`, `test_a_recurring_issue_is_addressed_by_the_comment_the_card_quotes`, `test_the_loop_does_not_supply_the_card_address` |
| 9 | **the review's address check removed** — the critique accepting a card whose address names a comment the chain does not hold | `test_the_review_checks_the_card_address_and_not_its_word` — exactly one |

## 5. What was measured, and on what tree

**Local, incremental, at commit `44ea84e` plus this record's own
commit.** The roles suite (eight spec witnesses, three trajectory, five
guidance, two critique, four orchestration), the demonstration's two,
the migration suite's table check, the store's parity checks — all
green, under the suite's environment rules (`TEMP`/`TMP`/`TMPDIR` at
`E:\labcairn-local\tmp`, a fresh `--basetemp` per run, statuses read
from the command and not from a pipe). `ruff`, `ruff format` and `mypy`
are clean on every file the work order added.

**The change of 2026-11-01 was measured on its own tree**, on this
record's own commit: the three roles' files, the loop's file, the
demonstration and the application layer's — **155 green**, under the
same environment rules (`TEMP`/`TMP`/`TMPDIR` under
`E:\labcairn-local\tmp`, a fresh `--basetemp` per run, statuses read
from the command and not from a pipe), and `ruff`, `ruff format` and
`mypy` clean on every file touched. **Each of the three mutations in
§4 was applied, and each reddened the witness named there** — and the
file was restored byte-for-byte after each, which the driver asserts
rather than assumes.

**The demonstration sends nothing.** Its one priced exchange runs
through `FakeProvider` with a scripted transcript; no network call is
constructed, and the work order §0 names the owner's authorisation as
the precondition of any real run. The roles' contracts refuse what they
do not list, and `MODEL_REQUEST` is on no role's list but B's — but the
demonstration exercises even B's through the fake, not through a
provider.

**No one-shot whole-suite run was made on the final tree.** The standing
decision of 2026-10-31 applies: after the machine's restart, the suite
is re-measured on the final tree and its figures go into this section.
The incremental evidence above is local until a runner says otherwise.

## 6. What this work order does not carry, and where that is written

- **Six new test files have no runner-measured cost.**
  `tests/test_agent_role_specs.py`, `tests/test_role_trajectory.py`,
  `tests/test_role_guidance.py`, `tests/test_role_critique.py`,
  `tests/test_role_orchestration.py` and
  `tests/test_guidance_loop_demo.py` are in no shard, and
  `test_ci_shard_coverage` is red **on purpose** — the costs are
  measured on the runner, and the fix is
  `python .github/remeasure_shards.py <run-id>` against the next run's
  logs. No shard partition was guessed.
- **The loop does not yet have a caller.** The three roles and the
  arrangement are modules with their own witnesses; the code that wires
  a real request into `decide_roles` and runs the roles it names is
  LC-P2-13's (the pilot's) work, and nothing here pretends otherwise.
- **The guidance is not good; it is consents, budgets, records and
  refusals.** Whether it helps a student is LC-P2-14's question, and
  nothing here answers it.
- **The card's address does not make the card writable into the ledger.**
  It makes the card **locatable**: a person can follow it to the comment
  behind it. **The ledger's `evidence_records` still require a source
  anchor the ledger can resolve**, and the card's address is not one —
  so §7.3's "the model's answer enters the ledger as a proposal a
  person can settle" is still not wired, and nothing here pretends
  otherwise. What changed is that the card is now *about* something a
  person can find.
- **And every card is now about a comment in the chain.** A card whose
  evidence names no comment, or names several, is refused by name. The
  abstention is untouched: it declares no evidence, so it has no
  address, and it says what was missing instead.

## The weakest point an independent review found

An independent read-only review re-applied every mutation in this
record's §4 and found all thirteen claims **hold**. Its weakest point
is the thinnest load-bearing surface here: **`DecisionLedger` is an
in-memory Python list.**

The "append-only audit trail" is a list in a dataclass: the dataclass
is not frozen, `_records` is a single-underscore attribute any holder
can rewrite, and the only structural guard on immutability is a
negative check that the object has no `update` and no `delete` — a
property asserted about an API surface rather than enforced by a type.
The overwrite mutation was caught, but only because the witness
inspects the trail's contents; a caller that mutates the list
directly reddens nothing.

**The remedy:** move the ledger into the store, the way LC-P2-01's
"the grant survives the process" did for approvals, and stamp the
version inside a single construction path.
