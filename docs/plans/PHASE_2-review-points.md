# Phase 2 review points — what to break, and where the witnesses are

**What this file is for.** The owner's ruling of 2026-10-29 moves the
review of a Phase 2 work order to **after the merge**, so that the
reviewer reads the merged tree rather than a branch that may still move.
A review that happens later needs something written down *now*, while the
work is still in front of the author: **the list of properties, the
witness that carries each one, and the mutation that should turn it
red.** Without it, "review it later" becomes "review whatever looks
interesting then", and the review is worth less than the merge it follows.

**What it is not.** It is not the review, and it is not a status board.
The review is somebody else's reading of the merged tree; this is the
author's statement of **what could be broken there**, so that the reviewer
knows where to push.

**How to use it.** Each row names a property, the witness that carries
it, and a mutation to apply. Apply the mutation. **The witness must go
red.** A witness that stays green is either a survivor or a mutation that
never took effect, and the two are told apart the same way every time:
**look at what the code did, not at what the test said.**

---

## The rules the reviewer is held to

1. **A mutation must make an assertion fail.** A change that leaves the
   suite green has not been shown to be harmless; it has been shown to be
   *invisible to the witness*, and that is the thing worth knowing.
2. **A survivor is checked for having been applied at all.** Inserting
   `if False: pass` in front of a check does not remove the check — and
   reporting that as "the mutation survived" is a false negative that
   looks like a success. LC-P2-06's own mutation table records the
   attempt that did this, and what it took to find it.
3. **The witness must fail for the property.** A test that goes red
   because of an unrelated encoding or lint matter is not a witness of
   that property. When a test goes red, ask what made it red.
4. **The state is the assertion, not the adapter.** A witness that reads
   the store is worth more than one that calls the code that writes the
   store; the second cannot tell a wrong write from a wrong read.
5. **A claim about a number is anchored to the commit it was measured
   at.** The numbers in the acceptance records carry their commit, and a
   number does not carry to another commit unless the bytes it depends on
   did not change.

---

## LC-P2-06 — Data governance, consent and access

**The acceptance record:**
[`docs/acceptance/LC-P2-06-acceptance.md`](../acceptance/LC-P2-06-acceptance.md)
**The task breakdown:**
[`docs/plans/LC-P2-06-task-breakdown.md`](LC-P2-06-task-breakdown.md)
**The design:**
[`docs/adr/ADR-0015-dataset-consent-and-access.md`](../adr/ADR-0015-dataset-consent-and-access.md)

### The properties, and what to break

| # | The property | The witness | The mutation to apply |
|---|---|---|---|
| 1 | **The absence of a row is the refusal.** A use with no grant is refused with a reason, and refused *normally* rather than by an exception. | `test_no_grant_is_a_refusal_and_not_an_exception` | Make the empty-`candidates` branch return an allowing decision. |
| 2 | **The permission, the purpose, the destination and the scope are four independent axes**, and a grant on one does not answer for another. | `test_a_grant_for_another_subject_does_not_answer_for_this_one`, `test_a_grant_for_one_destination_does_not_authorise_another`, `test_a_grant_for_another_purpose_is_refused_by_purpose`, `test_a_grant_whose_scope_does_not_reach_the_material_is_refused` | Drop the `permission` clause from the covering test and watch a read grant answer for a transmission. This is the mutation that makes the whole table collapse into one axis. |
| 3 | **The owner's identity authorises nothing.** `owner_id` records *whose* project this is; it is not authentication. | `test_the_owner_scope_authorises_nothing` | Let the covering test accept a grant on the strength of its scope alone, and let the no-grant branch name the owner as a reason. |
| 4 | **A withdrawn grant is not a grant that was never made.** The refusal says so, and says who and when. | `test_a_withdrawn_grant_is_refused_as_withdrawn`, `test_a_withdrawal_records_who_and_when` | Report a withdrawn grant as "no grant". The two are the same refusal to a reader and different questions to a person. |
| 5 | **The withdrawal is not a deletion.** The row is kept, and the copies derived from it are addressable and stale. | `test_the_grant_row_is_kept_and_not_deleted`, `test_a_withdrawn_grant_invalidates_the_copies_derived_from_it`, `test_the_withdrawal_keeps_the_copies_addressable` | Delete the row on withdrawal, and watch the copies keep their provenance and their freshness. |
| 6 | **A copy whose grant is not on the record is stale too.** "I cannot find the grant" is not "the grant is fine". | `test_a_copy_whose_grant_is_not_on_the_record_is_stale`, `test_the_stale_copies_are_listed_and_not_a_promise` | Treat a missing grant as a live one. This is the wrong direction of error, and it is silent. |
| 7 | **The window is both ends.** A grant for a future window does not permit a use today. | `test_a_grant_that_has_not_opened_yet_is_refused_as_such`, `test_an_expired_grant_is_refused_as_expired` | Drop the lower bound of the window. |
| 8 | **An expired grant is reported as expired**, not as "no grant". | `test_an_expired_grant_is_refused_as_expired` | Let the expiry be found by the closest-grant ranking instead of by the grant's own condition — the row still says `active`, so the ranking loses the reason. |
| 9 | **The transmit gate runs before the approval is consumed.** Asking is not spending. | `test_the_transmit_check_runs_before_the_approval_is_consumed`, `test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent` | Consume the approval first and check afterwards. The refusal is still correct and the person still pays. |
| 10 | **The two gates are two gates.** A read grant is not a transmit grant, and one does not imply the other. | `test_a_read_grant_does_not_authorise_a_transmission`, `test_a_grant_for_one_destination_does_not_authorise_another` | Merge the transmit grant into the operation approval. The default-deny for transmission then has no representation. |
| 11 | **A refusal names the missing permission and what would satisfy it.** | `test_a_refusal_names_what_would_satisfy_it` | Make the refusal say only "no". True and useless. |
| 12 | **The schema refuses the rows the design names**, and holds no row shape that means "denied". | `test_a_transmit_grant_with_no_destination_is_refused`, `test_a_read_grant_with_a_destination_is_refused`, `test_a_withdrawal_with_nobody_behind_it_is_refused`, `test_a_permission_outside_the_vocabulary_is_refused`, `test_the_table_holds_only_grants_and_therefore_has_no_way_to_say_denied` | Write the rows the schema must refuse and watch the database accept them. |
| 13 | **The archive is not opened at all without a grant.** | `test_material_with_no_grant_is_not_readable`, `test_the_archive_guards_refuse_what_the_design_names` | Remove the grant gate, or move it after the archive is opened. **The order is the property**: a refusal that reads the file to find out how big it is has already done the thing the grant forbids. |
| 14 | **The macro is refused, not cleaned.** A refusal is honest; a partial acceptance is not. | `test_a_macro_enabled_document_is_refused_not_cleaned`, `test_the_archive_guards_refuse_what_the_design_names` | Skip the macro check. |
| 15 | **No real material reaches the repository, a CI artefact, or the public evaluation corpus.** | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` | Leave a material file in the working tree, uncommitted and unignored — **the build backend does not read `.gitignore`, so it lands in the source distribution.** Then commit one that is not on the allowed list, then change one byte of the public corpus. |
| 16 | **Every refusal joins the enumeration the CLI renders**, so a reason nobody renders is a reason nobody sees. | the existing enumeration witness, `test_cli_refusal_enumeration.py` | Remove one consent reason from the enumeration and watch the two vocabularies drift apart. |
| 17 | **Every test file is in exactly one gate class, and says so itself.** A file in no class is a test CI never runs and whose cases enter no denominator. | `test_the_partition_files_every_test_file_exactly_once`, `test_a_file_that_declares_no_protocol_marker_is_in_no_protocol_class` | Remove a file from the partition, or change its class without changing its own `pytestmark`. |
| 18 | **The demonstration runs, and a test runs it.** | `test_the_consent_demo_runs`, `test_every_step_ran`, `test_the_demonstration_says_the_things_that_matter` | Invert one of the demonstration's checks. The exit code carries every claim, so the inversion shows up as a non-zero exit. |
| 19 | **A grant whose window has closed is not a live grant.** The copies made under it are stale, and the copy check and the permission check ask one question of one grant at one moment. | `test_a_grant_whose_window_has_closed_makes_its_copies_stale`, `test_the_copy_check_and_the_permission_check_do_not_disagree`, `test_the_stale_copies_include_the_ones_whose_grant_ran_out` | Make the copy check read the grant's `state` column instead of asking the grant. **Nothing in the product writes `state='expired'`**, so that branch is dead and the expiry half of the propagation never fires — **and a witness that builds the expired grant by hand survives the mutation.** |

### What this work order does not claim

**These are the places a reviewer should push hardest, because they are
where a claim could be true of the code and false of the product.**

- **A copy that was already used cannot be recalled.** The propagation
  makes the *next* use impossible. A reading that says the withdrawal
  undoes what has already happened is reading more than the mechanism
  does.
- **The material's own storage is not here.** This work order says who
  *may* use material; where the material lives is LC-P2-08's and
  LC-P2-09's.
- **A copy written before the mechanism existed has no provenance to
  check.** The mechanism is a fact about a copy's record, and a copy with
  no record has none.
- **The grant-issuing policy is a person's.** The machinery enforces a
  policy; it does not decide who may grant what.
- **No model is called and no money is spent.** LC-P2-01's path is where a
  call happens, and the owner's authorisation is a precondition there.

---

## LC-P2-08 — The paper project and the version graph

**The acceptance record:**
[`docs/acceptance/LC-P2-08-acceptance.md`](../acceptance/LC-P2-08-acceptance.md)
**The task breakdown:**
[`docs/plans/LC-P2-08-task-breakdown.md`](LC-P2-08-task-breakdown.md)
**The design:**
[`docs/adr/ADR-0014-paper-revision-provenance.md`](../adr/ADR-0014-paper-revision-provenance.md)

### The properties, and what to break

| # | The property | The witness | The mutation to apply |
|---|---|---|---|
| 1 | **A version graph, never a version list.** The process branches, so a column holding one parent cannot hold two. | `test_a_branch_is_representable` | Put the parent back into a column on `paper_versions`. |
| 2 | **Two files with the same name and different bytes are two versions**, and two with the same bytes are one. | `test_two_files_with_the_same_name_and_different_bytes_are_two_versions`, `test_the_same_bytes_are_one_version_whatever_the_name` | Decide identity by name, and then by content alone. **Both directions have to break separately**: the first merges two versions, the second splits one. |
| 3 | **The order is never taken from a file name or an mtime.** | `test_a_file_name_never_decides_the_order`, `test_a_modification_time_never_decides_the_order` | Sort by name, or by modification time. **A timestamp is the tempting one** — it is always there, and it is wrong whenever the file was copied. |
| 4 | **A proposal with high confidence is still unaccepted.** The confidence is not the decision. | `test_a_confident_proposal_is_still_unaccepted` | Accept by confidence. |
| 5 | **An edge that claims a human acceptance must name the acceptor**, and an edge with `source='evidence'` may not name one at all. | `test_an_edge_with_no_acceptor_is_refused`, `test_a_proposal_wearing_a_persons_name_is_refused` | Drop the constraint, or make the model's refusal of a proposal naming an acceptor disappear. |
| 6 | **The alignment refuses to decide when the evidence points two ways.** | `test_the_alignment_refuses_when_the_evidence_points_two_ways` | Remove the ambiguity margin, so a near-tie always decides. |
| 7 | **Two drafts whose prose matches and whose numbers differ are two versions.** | `test_two_drafts_that_differ_only_in_their_results_are_two_versions` | Collect **no numbers** in the fingerprint. |
| 8 | **A missing round is reported, and no version is invented to fill it.** | `test_a_missing_round_is_reported_and_nothing_is_invented` | Renumber the gap away, or invent the round. |
| 9 | **A correction is a new version of the edge, and the old one stays readable.** | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` | Overwrite the proposal instead of superseding it. |
| 10 | **An edge whose parent is outside the project is refused.** | `test_an_edge_to_a_version_outside_the_project_is_refused` | Allow the cross-project edge. **A CHECK constraint cannot catch this one** — it is a fact about three rows — so the model has to say it. |
| 11 | **A version with no established parent is `unresolved`, and it is listed.** | `test_a_version_with_no_established_parent_is_unresolved_and_listed` | Make the unresolved version disappear, or make it look established. |
| 12 | **A rejection writes no edge and keeps the proposal.** | `test_a_rejection_writes_no_edge_and_keeps_the_proposal` | Discard the proposal a rejection was about. |
| 13 | **The demonstration runs, and a test runs it.** | `test_the_paper_version_demo_runs` | Invert one of the demonstration's checks. |
| 14 | **A change's words and its address travel together, and the file agrees with the row.** | `test_a_revision_event_carries_the_text_and_the_place_of_the_change` | Store the address and drop the text, or store the text and re-point the address. |
| 15 | **A deletion keeps its text and is addressed in the rejected view.** | `test_a_deletion_keeps_its_text_and_is_addressed_in_the_rejected_view` | Address every event in the accepted view. **The deleted text is not in the accepted view at all**, so a reader that works in one view cannot cite a deletion. |
| 16 | **A missing author or date is unknown, and the absence is named.** | `test_a_revision_with_no_author_or_date_is_unknown_and_never_guessed` | Guess the author from the file's name or its mtime, or write an empty string and call it unknown. |
| 17 | **Recording the same version twice is the same rows.** | `test_recording_the_same_version_twice_is_the_same_rows` | Mint the id from the insertion order. |
| 18 | **A row whose text no longer matches the file is refused as stale, not re-pointed.** | `test_a_revision_whose_text_no_longer_matches_is_refused_as_stale` | Overwrite the row with the newly read text. **A silent re-point is the failure the whole table exists to prevent.** |
| 19 | **A manuscript whose bytes changed under its name is refused.** | `test_a_manuscript_whose_bytes_changed_under_its_name_is_refused` | Parse the file without comparing its bytes with the version's. |
| 20 | **A denial of the material writes nothing.** | `test_a_revision_event_is_not_recorded_when_the_policy_denies_the_material` | Record the events first and ask afterwards. |
| 20a | **A listing drops the events of denied material rather than refusing.** | `test_a_listing_drops_the_events_of_denied_material` | Return the events anyway, or refuse the whole listing. |
| 20b | **A comment and a change in one manuscript are two facts, and the chain asserts no correspondence nobody recorded.** | `test_a_comment_and_a_change_in_one_manuscript_are_two_facts` | Join the two, or drop the comment because a change exists in the same manuscript. **The corpus's richest sample is one person who both rewrote the text and wrote a remark about it, and the two are not one thing.** |
| 20c | **The four kinds of change are told apart, and an empty marker is never counted as a change.** | `test_the_four_kinds_of_change_are_told_apart` | Count the empty marker as a change, or count a space as a word. **One reviewer's copy in the corpus holds 58 revision elements and 32 changes** — the other 26 are cursors left behind, and a panel drawing "58 changes" would be drawing a number the file does not support. |
| 21 | **The schema cannot express why a change was made.** | `test_the_schema_cannot_express_why_a_change_was_made`, `test_threat_model.py::test_the_revision_events_cannot_carry_a_reason` | Add a column for the reason, or a foreign key to the comments. **This is the property that keeps a reviewer's silence from becoming a rule.** |
| 22 | **Each of the schema's rules refuses the row that breaks it.** | `test_the_schema_refuses_a_revision_event_that_breaks_its_rule` (twelve cases) | Remove a constraint from the table **and** from the migration. **Removing it from one only is caught by the parity test instead, which is a different witness.** |

### What this work order does not claim

- **A similarity score is not a fact about the document's history.** It is
  evidence about a proposal, and the proposal is not the decision.
- ~~**The version graph is presently fed by hand.** LC-P2-07's reader
  produces the revision events these tables hold, and nothing writes them
  into the store yet.~~ — **closed 2026-11-01.** The seam is wired: the
  events are stored, read back and measured over 897 real tracked changes.
- **The revision events are not on the event stream**, so they cannot be
  replayed from it. ADR-0017 D8 puts the chain's four objects there, and
  this is a fifth object waiting for a fifth event.
- **The fidelity measurement over the real material is local**, not a
  runner's; the record names the machine and the date.
- **No real material in the tests.** Everything the tests measure is
  synthetic; the real corpus was measured by a script, and a real
  manuscript brings run fragmentation inside a revision that a synthetic
  corpus does not.

---

## LC-P2-09 — The feedback chain

**The acceptance record:**
[`docs/acceptance/LC-P2-09-acceptance.md`](../acceptance/LC-P2-09-acceptance.md)
**The task breakdown:**
[`docs/plans/LC-P2-09-task-breakdown.md`](LC-P2-09-task-breakdown.md)
**The design:**
[`docs/adr/ADR-0017-feedback-chain.md`](../adr/ADR-0017-feedback-chain.md)

### The properties, and what to break

| # | The property | The witness | The mutation to apply |
|---|---|---|---|
| 1 | **A comment is an observation with two addresses** — what was written, and where it was written about. | `test_a_feedback_row_carries_both_addresses` | Keep only one address. |
| 2 | **The anchor's text and the offsets agree**, in the version the row names. | `test_the_anchored_text_agrees_with_the_offsets_in_the_version_named` | Return `""` for the text, or cut it from a different baseline. |
| 3 | **Unknown is a value**: no author, no date, an unpaired range. | `test_a_missing_author_or_date_is_unknown_and_never_guessed` | Fall back to the file's mtime, or to an empty string. **An empty string is the tempting one** — it is a value, and it is not the unknown. |
| 4 | **A feedback row names the version it was written against**, and one that names none is refused. | `test_a_feedback_row_names_its_version_and_one_that_names_none_is_refused` | Make the version default to the project's first one. |
| 5 | **A comment that cannot be anchored is still a comment.** | `test_an_unanchorable_comment_is_still_a_comment` | Drop the unanchorable comment. |
| 6 | **An edit names who made it**, and a model's change is not the advisor's. | `test_an_edit_names_who_made_it` | Give `actor_kind` a default. **ADR-0017 D4 exists because that default is how a model's change becomes the advisor's.** |
| 7 | **A response is a judgement with evidence**, not a status. | `test_a_response_state_needs_a_decision_and_its_evidence` | Let a non-`pending` state be written with no decider, no moment or no evidence. |
| 8 | **A comment with no response is listed as unaddressed**, not omitted. | `test_an_unanswered_comment_is_listed_as_unaddressed` | Skip the comment with no response. **An empty answer looks like "nothing outstanding".** |
| 9 | **A change that does not answer the comment is recorded as `not_addressed` and exists.** | `test_a_change_that_does_not_answer_is_recorded_as_not_addressed` | Drop the row. |
| 10 | **A partly-answering change is `partially_addressed`, not `addressed`.** | `test_a_partial_answer_is_not_an_answer` | Promote the partial answer. |
| 11 | **No `issue_key` is inferred from the text.** | `test_no_issue_key_is_inferred_from_the_text` | Derive a key from the wording. **The same wording is not the same issue.** |
| 12 | **Two comments with the same key in different versions are one recurring issue.** | `test_the_same_issue_recurring_is_visible_as_one_issue` | Group by version, so the recurrence disappears. |
| 13 | **An assessment carries its own evidence**, and acceptance is not evidence of correctness. | `test_an_assessment_cannot_derive_correctness_from_acceptance` | Add `change_accepted` to the allowed bases. **Acceptance is a fact about the process, and correctness is a claim about the science.** |
| 14 | **The four chain events are annotations** with a registered payload schema, and **the operations emit them.** | `test_the_chain_events_are_annotations_with_registered_payloads`, `test_the_feedback_demo_runs` | Make an event carry a `run_id` or a `transition`; and remove the emit from one `record_*` operation. **The second is the one this work order found unheld.** |
| 15 | **A version and an edge can be stored**, and a stored edge round-trips through the models' checks. | `test_a_stored_edge_round_trips_through_the_models_own_checks` | Read the row's fields back without asking the contract. |
| 16 | **A `pending` response is not an event.** | `test_a_response_with_no_judgement_made_is_not_an_event` | Let the payload accept `pending`. "No row" is how "unanswered" is represented, and an event that says otherwise says the opposite of what it means. |
| 17 | **A model's candidate carries no `comment_locator`.** | `test_a_candidate_does_not_claim_the_advisors_words` | Let a candidate carry the locator — that is ADR-0016's third promotion path. |
| 18 | **The demonstration runs, and a test runs it.** | `test_the_feedback_demo_runs` | Invert one of the demonstration's checks. |

**Six of these were applied and watched** (the acceptance record's §4);
**the rest are this reviewer's pass.** A mutation that was never applied
reports as a surviving mutation, so check the diff before believing a green
result — the project's own lesson, and the one this file exists to keep.

### What this work order does not claim

- **It does not say whether the advisor was right.** It says what was
  answered, by what evidence, and what a later assessment concluded.
- **It does not render the chain.** The tables hold it; whether a report
  shows it is the owner's decision.
- **It does not identify people.** It records kinds of actor and plain
  ids; ADR-0015 D6's conditions are open.
- **It does not let a model originate guidance or decide a response.**
  That is LC-P2-12's and ADR-0016's.

---

## LC-P2-12 — The three-role guidance loop

**Task breakdown:**
[`LC-P2-12-task-breakdown.md`](LC-P2-12-task-breakdown.md) ·
**Acceptance:**
[`../acceptance/LC-P2-12-acceptance.md`](../acceptance/LC-P2-12-acceptance.md)

The reviewer is asked to break each claim below. Each is carried by the
witness named; the acceptance record §4 lists the mutations that were
already applied and what they reddened.

| # | The claim | The witness | How to break it |
|---|---|---|---|
| 1 | **A role's contract is a versioned row, and the version is stamped on every output.** | `test_a_role_spec_is_versioned_and_the_version_is_on_the_output` | Return an output whose `role_version` is not the contract's. **An output that does not say which contract governed it cannot be replayed against that contract.** |
| 2 | **A role may exercise only what its contract lists, and the refusal is machine-readable.** | `test_a_call_outside_the_role_spec_is_refused` | Turn the refusal into a message. **A caller that can only read prose cannot branch on it.** |
| 3 | **The five forbidden actions are closed, and a role holds no direct path out** — no socket, no requests, no database connection. | `test_a_role_holds_no_direct_path_out`, `test_an_unknown_capability_or_action_is_refused_by_name` | Add a sixth action as a string in a spec; or import `httpx` inside a roles module. **The first is refused by vocabulary, the second by the watched import surface.** |
| 4 | **Role A proposes judgements, never facts** — the candidate type has no `comment_locator` field, and the advisor's words must sit verbatim on the chain. | `test_role_a_proposes_judgements_and_never_facts` | Add the field; or accept a paraphrase. **The shape itself is the refusal; a paraphrase would be A putting words in the advisor's mouth.** |
| 5 | **The version order is walked over accepted edges, never spelled by name** — a version outside the graph is refused, a fork is refused. | `test_role_a_does_not_order_versions_by_name_or_invent_a_round` | Sort by `version_label_raw`. **`manuscript-2.txt` before `manuscript-10.txt` is the dictionary's order, not the paper's.** |
| 6 | **An abstention is a result, and it names what was missing.** | `test_insufficient_material_produces_a_named_abstention` | Allow an empty `missing`. **An abstention that names nothing is a shrug wearing a record's clothes.** |
| 7 | **A rule is cited with its counter-examples, and they cannot be trimmed.** | `test_a_card_cites_a_rule_with_its_counterexamples` | Return the citation without the cases against the rule. **A rule without its failure cases is an advertisement.** |
| 8 | **A verdict is `inferred` and writes no store row** — two models agreeing promotes nothing. | `test_a_verdict_does_not_promote_a_proposal` | Let the review persist; or let `grade` be raised to `human_verified`. **The store row count is counted, not asserted, so the first shows immediately.** |
| 9 | **The critique's counter-evidence is its own retrieval**, not a field B filled in. | `test_role_c_reads_the_sources_and_its_own_counterevidence` | Pre-fill `counter_evidence` from the card. **Then C reads B's homework and the independence is a word.** |
| 10 | **The routing is data** — the tables are parameters, the kind vocabulary is closed, every role runs for a recorded reason. | `test_the_roles_that_run_are_the_ones_the_request_needed` | Route an unknown kind by a default. **A default is a branch wearing data's clothes; there is no swarm.** |
| 11 | **An unmeasurable cost refuses, and a retry is the same plan.** | `test_an_unmeasurable_cost_refuses_and_a_retry_does_not_pay_twice` | Let an unpriced spec send; or make `retry` build a second plan. **A budget whose price is unknown fails closed; a retry that pays twice pays for a guess.** |
| 12 | **A person's decision is audited** — appended, attributed, never overwritten. | `test_a_human_decision_on_a_card_is_audited` | Add an `update` to the ledger. **A decision a person made stays made; a change of mind is a second record.** |
| 13 | **The demonstration sends nothing, and its exit code means something.** | `test_the_guidance_loop_demo_runs`, `test_the_demonstrations_exit_code_still_means_something` | Neuter the planting and watch the second test stay green — it does not. **A demonstration whose `check()` is neutered prints the same lines and exits zero.** |

---

## LC-P2-11 — The mentor guidance memory

**Task breakdown:**
[`LC-P2-11-task-breakdown.md`](LC-P2-11-task-breakdown.md) ·
**Acceptance:**
[`../acceptance/LC-P2-11-acceptance.md`](../acceptance/LC-P2-11-acceptance.md)

The reviewer is asked to break each claim below. Each is carried by the
witness named; the acceptance record §4 lists the mutations that were
already applied and what they reddened. **A reviewer who finds this section
missing must say so before reviewing anything else**: it was absent until an
independent review on 2026-10-31 looked for it, which is the task
breakdown's §7.6 obligation unfulfilled.

| # | The claim | The witness | How to break it |
|---|---|---|---|
| 1 | **The state machine is closed** — `candidate → confirmed \| disputed \| withdrawn`, and only a person moves a rule out of `candidate`. The API guard and the migration's CHECK are two walls, and the ORM's mirror is a third. | `test_the_schema_refuses_what_the_api_refuses`, `test_the_migrated_schema_matches_the_orm_models` | Widen the CHECK in migration 0015 to admit `proposed`; or widen the models-side mirror. **The first is caught by the schema witness, the second by the parity test — apply each mutation against both files, or the answer is a false negative.** |
| 2 | **The confirmer is a second reader**: whoever proposed a rule cannot confirm it, and `model_proposal` is refused as a confirmer like any other proposer. | `test_the_proposer_cannot_confirm_their_own_rule` | Drop the `confirmed_by == row.proposed_by` refusal. **A rule its own author confirms is an echo wearing a rule's clothes.** |
| 3 | **A source stands or falls at query time, by its state and not by a clock** — the chain's presence under the key, the reader's reach through the permission layer, and a judgement that says the change answered. | `test_a_withdrawn_source_invalidates_its_rule_and_says_so`, `test_a_rule_outside_the_readers_consent_is_not_retrieved`, `test_the_memory_reads_through_the_consent_layer` | Discard the permission layer's answer and return every path; or neuter the standing guard. **The second is a common exit for all three ways a source dies, so it reddens more witnesses than the record's table lists.** |
| 4 | **The invalidation is not silent**: a rule the memory stops serving is reported, each dead source saying which of the three ways it died. | the withdrawal witness's second half | Replace the invalidation report with `pass`. **A rule that stopped being served for a reason nobody was told is a rule that stopped being served.** |
| 5 | **Two conflicting rules are both returned, and neither wins by recency** — the ordering consults state and rule id, never a version or a timestamp. | `test_two_conflicting_rules_are_both_returned_and_neither_wins_by_recency` | Reverse the ordering key. **The order the witness asserts is the id order, so a seed where the two rules differ in version would tell a recency-key from an id-key apart — the current seed cannot, and that is a gap in the witness, not in the code.** |
| 6 | **The distillation may not invent a scope**: it has no scope parameter, the scope is assembled from the cases' anchored text, and a named key the chain holds nothing under is refused. | `test_a_rule_with_an_unsupported_scope_is_refused` | Take the scope from the caller's `rule_context`. **A scope the cases do not support is a rule about something that was never said.** |
| 7 | **A distilled rule is a candidate until a person confirms it**, and a suggestion retrieved often does not become a rule by being retrieved often. | `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it`, `test_a_frequently_retrieved_suggestion_is_still_a_candidate` | Confirm the rule as the model that proposed it; or promote on retrieval count. **Frequency is not consent.** |
| 8 | **The retrieval returns the source and its conditions, never a bare sentence.** | `test_the_retrieval_returns_the_rule_with_its_source_and_its_conditions` | Drop the source from the returned hit. **A sentence without its source cannot be checked against anything.** |
| 9 | **A rule's problem comes from the closed vocabulary** — LC-P2-10's thirteen labels, imported rather than retyped, at propose, at distil, and at the query boundary. | `test_a_problem_outside_the_vocabulary_is_refused`, `test_the_query_filters_and_the_vocabulary_gates_it` | Accept a free-text problem type. **A vocabulary that can be widened at the door is a vocabulary.** |
| 10 | **The demonstration is run by a test, and its exit code means something.** | `test_the_guidance_memory_demo_runs`, `test_the_demonstrations_exit_code_still_means_something` | Neuter the planting and watch the second test stay green — it does not. **A demonstration whose `check()` is neutered prints the same lines and exits zero.** |

---

## LC-P2-01 — The model-call path

**Task breakdown:**
[`LC-P2-01-task-breakdown.md`](LC-P2-01-task-breakdown.md) ·
**Acceptance:**
[`../acceptance/LC-P2-01-acceptance.md`](../acceptance/LC-P2-01-acceptance.md)

The reviewer is asked to break each claim below. Each is carried by the
witness named; the acceptance record §3 lists the mutations that were
already applied and what they reddened.

| # | The claim | The witness | How to break it |
|---|---|---|---|
| 1 | **The bridge is at the caller, and `providers/` still imports nothing of the permission layer.** The call site hands the caller's `ApprovalUse` straight through and inherits `transmit_request`'s order as the property it is — the material gate first, then the approval. | `test_providers_does_not_import_the_permission_layer` (the import surface), `test_the_material_gate_runs_before_the_approval_is_spent` and `test_an_unapproved_model_request_refuses_and_sends_nothing` (the order) | Move the `send` call ahead of the gates. **The two order witnesses redden at once, which is what shows they watch the same line from its two sides; the import-surface witness does not redden, because an import is not an order.** |
| 2 | **A fresh checkout cannot spend money by accident**: `httpx` is declared at a chosen version, and the tree carries no **route** to a supplier: no configuration file, no price, no capability claim, and no authorised supplier's model id or endpoint. | `test_httpx_is_a_declared_dependency`, `test_no_model_id_endpoint_or_price_is_written_into_the_tree`, and the six witnesses in `tests/test_provider_credentials.py` that read the checkout | Remove the declaration; or write a model id into any `src/` file. **A supplier's identity is the operator's configuration, never the tree's.** |
| 3 | **The budget's preflight runs before the gate**, so an unmeasurable refusal costs the person nothing. | `test_a_cost_ceiling_fails_closed_when_the_price_is_unknown` | Move the preflight past the approval consumption. **Exactly that witness reddens: the position is the property.** |
| 4 | **A schema request the probe does not license is refused before a socket exists** — and the two ways not to be licensed name themselves, because their remedies differ. | `test_an_unprobed_provider_is_blocked` | Drop the schema-ability check, or collapse the two refusals into one. **The first asks a provider to try; the second sends a caller to remedy a probe that has not run.** |
| 5 | **What came back is judged, not accepted** — an empty result is not a result, and an undecodable answer is a refusal naming what was expected. | `test_an_empty_result_is_not_a_result`, `test_an_undecodable_answer_is_refused_with_the_expectation` | Pass the decode failure through as an answer; or drop the empty check and let `{}` fall to the decoder. **Illegal output must never become evidence by accident.** |
| 6 | **The refusal does not unstate the call**: the wire carried the request, the approval is spent, and the exchange record stays. | the A10 witness's exchange assertions | Move the emit after the decode. **The log and the wire must agree about whether a call happened.** |
| 7 | **A model's answer enters as a proposal, bound before it can be cited**, and the constructor — not the path — holds the line to `planned`. | `test_a_models_answer_enters_as_a_proposal_and_is_bound` | Grade the status to `EXTRACTED`; or drop the locator binding. **A model's say-so is never a reader's record, and an unpinned claim cannot be checked.** |
| 8 | **The exchange record is safe to persist by construction** — digests and counts, the credential by its fingerprint, no field a plaintext key could occupy. | `test_the_transcript_and_usage_land_and_no_key_is_written` | Send a key-shaped string as the fingerprint. **Exactly that witness reddens: the shape is the proof, not the docstring.** |
| 9 | **The path's refusals are in the layer's vocabulary, closed both ways**, and every refusal is looked up rather than hand-written. | `test_the_model_path_refusals_are_in_the_layers_vocabulary`, `test_the_path_raises_through_the_vocabulary` | Add an orphan `MODEL_` member; or construct the layer's error directly in the module. **A name no refusal carries is as dead as a refusal no surface can name.** |
| 10 | **An unanswered call is unknown and not a success, and one approval pays for one call.** | `test_an_unanswered_request_is_unknown_and_not_a_success`, `test_a_retry_does_not_pay_twice` | Record an exchange on the unanswered path; or let a spent approval be consumed again. **A record shaped like an answer would be a lie about what came back.** |
| 11 | **The demonstration sends nothing, and its exit code means something** — consented, budgeted, recorded, and refused before a socket exists. | `test_the_model_request_demo_runs`, `test_the_demonstrations_exit_code_still_means_something` | Neuter the planting and watch the second test stay green — it does not. **A demonstration whose `check()` is neutered prints the same lines and exits zero.** |

---

## How this file grows

**Each work order adds its own section, and the file is edited in the
same commit as the work order it describes.** A review points file that
is written after the merge is a file written by memory, and memory is
what this project has been bitten by before.

One section is still to come: **LC-P2-07**, the DOCX revision and comment
fidelity — its fidelity baseline already carries its own numbers and its
own mutations, and the properties it names are the ones a reviewer should
break.
