# LC-P4-PILOT — a document with no comment that also names a rule

**Ticket:** LC-P4-PILOT, the path the comment-less run's record left open:
*"a run over a document with no comment and a rule the card would cite"*.
**Date:** 2026-11-27.
**Tree:** based on `main` @ `21ea0725ebd4dd833d50eeacd4698e31c4b34cd1` ("Say in the review that the tree caught
one of its own sentences"), worktree `charming-ellis-dffca4`, Windows 11 Pro
(10.0.26300 x64), Python 3.12.13.
**Status:** local evidence only. No push, no pull request, no CI run, no merge.
**Command:** `labcairn roles run --role <role> --project <project id>
--issue-key <key> --rule <rule id> [--json]`.

**What is claimed here.** The comment-less run's record said the rule a
request names *"is not fetched"*. The measurement says it is: the question is
built before the comment-less branch is consulted, and the rule is read there.
This record **measures both directions of that path** — a rule the memory
serves, and one it does not hold — **states which answer the product's promises
support**, and **measures what the comment count's narrowed scope would have
answered** before it was changed.

**What is not claimed.** That a real model was asked — it was not, and it could
not have been: the comment-less run reaches no wire by construction. The
document's material is the project's own fixture, never the pilot's, and no
request left the machine.

---

## 1. The path, measured

**The shape.** A project with two versions in an accepted edge, **one tracked
change and no comment at all** — the third pilot's shape, and the shape the
comment-less run exists for. The change is a `ins` by `reviewer-a` on the
methods paragraph. The roles' contracts are planted for all three roles.

**The rule.** A rule is learned from that change: `propose_rule` names the
revision event's own id as its source — :func:`revision_source_key` says the
key *is* the event id, because the product mints it and a caller may not write
one — and `confirm_rule` is a second reader's act. The memory then serves it:
`cite_rule` returns the citation, version 1, with the counterexamples the
memory holds.

**The two answers.** The same document, the same request, the same plan,
differing in one value — the rule's id:

| the rule the request names | what the product answered |
| --- | --- |
| the rule the memory serves | the ticket carries **no approval**; the question's `rule_citation` names the rule; the run **abstains** over the missing comment; nothing was sent |
| `rule-nowhere` | the request is **refused** with `role_rule_not_in_the_memory`; the message names the id; the refusal happens at the ask step, before an approval exists; the refusal is recorded in the log |

**So the record's sentence was wrong in one direction only.** The rule **is**
fetched, and a missing rule refuses the whole request before the chain's "no
comment" state is consulted. What the record left open was the other direction:
what the product answers when the memory *does* hold the rule. It answers with
the comment-less run — the rule was read, the run abstains — and the result
carries no citation, because it carries no card.

---

## 2. What should happen, and what made that the answer

The comment-less run's record offered three answers, and they are not the same
product: **refuse** (what the code does), **abstain** (do not fetch the rule at
all), or **fetch and say the rule was found while the chain holds no comment to
apply it to**. The product's own promises support the first for a rule the
memory lacks, and the comment-less run for a rule it serves.

**The refusal is the request step's own promise, and the comment-less change
did not touch it.** `the_role_run_question` documents *"the memory holds no rule
under the id the request names"* as one of the refusals of building the
question. The change of 2026-11-27 narrowed a different clause — *"the chain
holds comments but none under the issue key"* versus *"no comment at all"* —
and a comment count cannot make the memory hold a rule. **The two are facts
about different stores**: the chain's count is a fact about the project's
material, and it cannot gain a comment from this request; the rule's presence
is a fact about the memory, and its id can be corrected or dropped. A refusal
names the fact with the remedy; an abstention here would name the document for
a mistake that is not the document's.

**Abstaining would make a rule id that names nothing indistinguishable from
one the memory serves.** A caller who passed a stale id would be told *"the
chain holds no comment"* and would learn nothing about the id; the same id
would fail later, on a document that does hold a comment, as a refusal about a
different request. That is a delayed failure with a different address, and
**the tree's own rule is that a run which quietly did less than it reported is
the failure the whole shape exists to prevent**. A rule the memory does not
hold is a mistake the product can name now.

**And the loop must not decide it.** *"The refusals are the roles' own. The
loop does not check the values it hands a role; the role does."* `cite_rule` is
the guidance role's read of the memory. Skipping it whenever the chain holds no
comment would make the loop decide, on the chain's state, a question the memory
answers — the second spelling of a rule the loop's docstring says it does not
keep. The code's order is the architecture's own: the **question** is built
first (the two-step design says the question is written down before a run
decides anything), and the comment-less branch belongs to the **run**.

**The third answer is refused because the citation belongs to a card.** The
product defines a citation as *"a rule the card cites"*; a run over a document
with no comment produces role B's abstaining card, which cites nothing. A
result that carried the citation anyway would state a citation no card makes.
**The information is not lost**: the ticket's question carries the citation, so
the ask step already says which rule was read and what its counterexamples are
— witnessed below. A result that repeated it would be the second place the same
fact is told, and the second place is the one that drifts.

**Consent is untouched in both directions.** A served rule does not change the
branch the run takes, so the run asks no approval, reaches no wire, writes no
exchange, and does not refuse for want of a provider. A rule the memory lacks
refuses before the consent is asked, so no approval is minted and there is
nothing to spend.

---

## 3. The witnesses

`tests/test_role_run_commentless_rule.py` (new, twelve witnesses) holds the
path, and `tests/test_role_run_commentless.py` gained the count witnesses:

| property | witness |
| --- | --- |
| the fixture's rule is one the memory serves | `test_the_rule_the_document_built_is_one_the_memory_serves` |
| a served rule does not stop the comment-less answer | `test_a_comment_less_run_that_names_a_served_rule_abstains` |
| the abstention names the comment, not the rule | `test_the_abstention_names_the_comment_and_not_the_rule` |
| the rule is read, and the ticket says which one | `test_the_ticket_names_the_rule_it_read` |
| the abstaining run carries no card that cites the rule | `test_an_abstaining_run_carries_no_card_that_cites_the_rule` |
| a missing rule refuses the request by the role's own reason | `test_a_rule_the_memory_does_not_hold_refuses_the_request` |
| the refusal names the rule and not the provider | `test_the_refusal_names_the_rule_and_not_the_provider` |
| a served-rule run asks no approval and reaches no wire | `test_a_served_rule_run_asks_no_approval_and_reaches_no_wire` |
| a missing rule refuses before any consent exists | `test_a_missing_rule_refuses_before_any_consent_exists` |
| the refusal is recorded in the log | `test_the_refusal_is_recorded_in_the_log` |
| the command runs a comment-less document naming a served rule | `test_the_command_runs_a_comment_less_document_that_names_a_served_rule` |
| the command refuses a missing rule by name | `test_the_command_refuses_a_missing_rule_by_name` |

**Every one of them was mutation-checked.** Each mutation was applied to the
worktree's `src/`, the witnesses were run, and the file was restored from git
afterwards. The table below is the measurement, not a plan.

| mutation | what it makes the product do | witnesses that went red |
| --- | --- | --- |
| skip the rule read when the chain holds no comment | the "abstain" answer: a missing rule no longer refuses | the ticket witness and **all five** refusal witnesses — the layer's two, the consent one, the log one, the command's |
| refuse whenever a comment-less request names a held rule | the "refuse always" answer | the abstaining run, the abstention's text, the ticket, the no-card witness, the served-rule consent witness, the command's run |
| mint an approval even when the chain holds no comment | consent asked for a call that will never be made | the served-rule run's consent witness (and the comment-less file's own consent witness) |
| name the rule in role A's abstention | an abstention about the request, not the material | `test_the_abstention_names_the_comment_and_not_the_rule` |
| attach the citation to the abstaining card | the "in between" answer | `test_an_abstaining_run_carries_no_card_that_cites_the_rule` |

**No witness is skipped, and every witness is green on the tree as committed.**
A test that failed for the fixture's own reason would not be a witness, so the
premise — the memory serves the rule — is a witness of its own.

---

## 4. What the count's narrowed scope would have answered

`read_document_shape` now counts **the project's** comments. It used to count
the comments on **the versions the caller named**, and the change's own witness
held only the new scope. **What the old count would have said in the same
situation was not measured — this window measured it.**

The shape both measurements use is the one the change was made for: a project
whose comment is written on the **second** version, under the key `iss-nowhere`
(the fixture's own key), while the request names only the **first** version.

| shape of the request | the narrowed count (old) | the project's count (new) | the product, over the old count | the product, over the new count |
| --- | --- | --- | --- | --- |
| key **not** named (`iss-elsewhere`) | **0** | **1** | abstains, saying the document holds no comment, and asks nobody's consent | refuses `role_comment_not_in_the_chain`: the key is the mistake, and it has a remedy |
| key **named** (`iss-nowhere`) | **0** | **1** | abstains **over the very comment the read under the key finds**, and asks nobody's consent | is not comment-less: it asks for the approval a model call needs |

**Both old answers were measured, not argued.** The predicate the old count
used is written out in the witness against the store; the shape the old count
produced is the read's own shape with that count substituted; and the run is
made over it. The witnesses are
`test_the_narrowed_count_would_have_made_a_commented_project_abstain` and
`test_the_narrowed_count_would_have_abstained_over_the_comment_it_was_asked_about`
in `tests/test_role_run_commentless.py`; reverting the count to the version
condition turns both of them, and the change's own witness, red.

**Which answer the product's promises support: the project's.** Two reasons,
both of them the change's own:

- **A key names a comment wherever it was written**, so a count narrowed to the
  versions the caller named contradicts the read under the key. The record's
  own sentence — *"the count and that read have to agree about the same fact"*
  — is what the narrowed count broke. The second row is the sharpest form: the
  read found the comment, and the count would have told the run there was
  nothing to find.
- **A count that is wrong about the material makes the run answer a different
  question.** The comment-less branch's promise is that *no comment at all* is
  a shape of the material. A narrowed count makes that promise false: it
  reports the shape of one round as the shape of the document. The project's
  count reports the document's shape.

**One sentence in `chain.py` was corrected while measuring this.** The count's
docstring said :func:`read_comments` *"answers for the whole project"*. It has
no project parameter; it narrows by neither version nor project. The sentence
now says so. What a key shared by two projects would do was **not** measured —
see what is still open.

---

## 5. The local measurement

**On the final tree** — this worktree, `main` @ `21ea0725ebd4dd833d50eeacd4698e31c4b34cd1` plus this window's
changes — read from each command's own exit status, not a pipeline's:

| command | reading |
| --- | --- |
| `python -m pytest tests/test_role_run_commentless.py tests/test_role_run_commentless_rule.py -q` | **32 passed** in 42.64s |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `585 files already formatted` |
| `mypy --strict` | `Success: no issues found in 510 source files` |

**The whole suite was run once, and on a tree one assertion short of this
one.** `test_the_command_refuses_a_missing_rule_by_name` was strengthened to
`EXIT_REFUSED` after the run had started, so the suite's reading — **11
failed, 6346 passed, 39 skipped** in 5317.66s (1:28:37) — is not carried here
as the final tree's number. Spending another 1.5 hours to absorb that one
assertion was not done; the test itself passed on the final tree inside the
32 above. **The eleven are itemised because the suite was red, not because
they are this record's evidence.** Each was re-run by itself on the final
tree, and none of them touches a file this window changed:

| failed test | re-run on the final tree | what it is |
| --- | --- | --- |
| `test_ci_shard_coverage.py::test_every_test_file_is_in_exactly_one_shard` | red | `test_role_run_commentless_rule.py` is in no shard — **the expected red**; the integrating session registers it |
| `test_ci_shard_coverage.py::test_the_recorded_costs_cover_every_test_file` | red | the same file has no measured cost |
| `test_evaluation_harness.py::test_the_partition_files_every_test_file_exactly_once` | red | the same file is in no gate class |
| `test_external_path_references.py::test_every_path_a_record_names_is_in_the_ledger` | red | **not this window's files**: the unledgered paths are named in `docs/acceptance/LC-P4-PILOT-report-evidence-gate-2026-11-27.md:87` and in a `-2026-11-28.md` record |
| `test_external_path_references.py::test_the_paths_are_where_the_ledger_says` | red | **machine state**: `E:/labcairn-local/tmp/mpl` is on disk (created 2026-11-27 19:46) and the ledger records it as absent |
| `test_fault_injection_e2e.py::test_a_crash_through_the_cli_leaves_the_task_state_on_disk` | **passed alone** (12.53s) | the suite hit `disk I/O error` at `PRAGMA journal_mode=WAL` — the error `db/session.py` documents as the crash-recovery shape — and it did not reproduce alone |
| `test_no_reference_leakage.py::test_wheel_installs_clean_and_imports` | red with `PYTHONPATH` set, **passed without it** | the worktree's `src` on `PYTHONPATH` shadowed the clean room's wheel |
| `test_outsider_path.py` (four tests) | red with `PYTHONPATH` set, **all four passed without it** | the walk copies `os.environ`; the inherited `PYTHONPATH` made the clone's run resolve the worktree's `labcairn`, which the walk's own "runs the clone's own code" check caught |

**The last two rows are this window's own running condition, not the tree's
property.** This window's brief required the worktree's `src` first on
`PYTHONPATH`; the tests that build a clean room or clone a repository inherit
that variable. Measured: the same tree, the same venv, and only `PYTHONPATH`
unset — `test_wheel_installs_clean_and_imports` and the four outsider-path
tests gave **18 passed** in 155.91s. **The shard registration is the one red
that is about this window's own files, and it is the integrating session's to
fix** — a file in no shard is a test CI never runs.

---

## 6. What is still open

- **`tests/test_ci_shard_coverage.py` is red on this branch, and it should be.**
  `tests/test_role_run_commentless_rule.py` is in no shard; the integrating
  session registers it in the manifest and in a shard after the batch merges.
  **A file in no shard is a test CI never runs**, and that is the first thing
  to fix — it is not this window's to fix.
- **The comment read has no project parameter.** :func:`read_comments` selects
  by issue key alone, while the count is the project's. Within one project the
  two agree about the comments the run is about; **a key shared by two projects
  would let the read reach the other project's comment, and what that does to a
  run was not measured.** Fixing it means deciding whether an issue key is
  global to the memory or local to a project — a decision this window did not
  make, and one that touches the guidance layer's own reads besides the loop.
- **The pilot's own material was not touched.** No request was made to any
  model, and nothing under the pilot workspace or the owner's corpus was read.
- **The comment-less run's own record still says its witnesses did not cover
  this path.** That record is corrected in place to point here.

---

## Files

| file | what changed |
| --- | --- |
| `tests/test_role_run_commentless_rule.py` | the new witnesses: the served rule, the missing rule, the ticket's citation, the abstaining card, consent, the log, the command |
| `tests/test_role_run_commentless.py` | two witnesses for what the narrowed count would have answered |
| `src/labcairn/application/chain.py` | the count's docstring: the read narrows by neither version nor project |
| `docs/acceptance/LC-P4-PILOT-comment-less-run-2026-11-27.md` | the open item is answered, and the count's unmeasured half is named |
| `docs/acceptance/LC-P4-PILOT-comment-less-and-a-rule-2026-11-27.md` | this record |

**No product behaviour was changed.** The measurement found the code's answer
to be the one the promises support: the rule is fetched, a missing rule
refuses, and a served rule leaves the comment-less run abstaining.