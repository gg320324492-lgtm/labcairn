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

### What this work order does not claim

- **A similarity score is not a fact about the document's history.** It is
  evidence about a proposal, and the proposal is not the decision.
- **The version graph is presently fed by hand.** LC-P2-07's reader
  produces the revision events these tables hold, and nothing writes them
  into the store yet.
- **No real material.** Everything measured here is synthetic; a real
  manuscript brings run fragmentation inside a revision that a synthetic
  corpus does not.

---

## How this file grows

**Each work order adds its own section, and the file is edited in the
same commit as the work order it describes.** A review points file that
is written after the merge is a file written by memory, and memory is
what this project has been bitten by before.

Two sections are still to come. **LC-P2-07**, the DOCX revision and
comment fidelity — its fidelity baseline already carries its own numbers
and its own mutations, and the properties it names are the ones a
reviewer should break. And **LC-P2-09**, the feedback chain, which is
where this line's `derived_copies` will point when a distilled rule is
made from a case.
