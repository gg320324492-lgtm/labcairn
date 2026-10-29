# LC-P2-06 / LC-P2-08 — independent review of the merged tree

**Work orders reviewed:** LC-P2-06 (data governance, consent and access) and
LC-P2-08 (the paper project and the version graph), as they stand in the
merged tree.
**The tree reviewed:** `ff93b1dc43a39d97bbb15ca37111397454d9d1e4`
(*Merge pull request #128 from gg320324492-lgtm/claude/p2-lc-p2-06*), which is
also `main` at the time of the review.
**Platform:** Windows 11 (10.0.26300) AMD64.
**Interpreter:** CPython 3.12.10 (msvc build, 64-bit).

**The work list** was
[`docs/plans/PHASE_2-review-points.md`](../plans/PHASE_2-review-points.md):
18 properties for LC-P2-06 and 13 for LC-P2-08, each with the witness that
carries it and the mutation that should turn it red. Every row below was
tried in the order the file names it, and every verdict is the result of
running the witness on the mutated tree — not a reading of the code.

**How the runs were made.** The repository's shared virtualenv at
`E:\LabCairn\.venv` carries an editable install whose `.pth` names
`E:\LabCairn\src` — the **main checkout**, not the review worktree — so a
mutation applied in this worktree would not have reached the code under test,
and every verdict would have been a verdict about a different tree. A
separate virtualenv was therefore created at `E:\labcairn-local\venv-review`
with its own launcher and its own `.pth` pointing at
`E:\LabCairn\.claude\worktrees\agent-ae5c38837ba16ad1d\src`, and
`import labcairn` was checked to resolve to that tree before any mutation
was applied. Each run used its own `--basetemp` and its own `TMPDIR`/`TEMP`/
`TMP`/`MPLCONFIGDIR` under `E:\labcairn-local\tmp`, outside the repository.

**Baseline.** Before any mutation: LC-P2-06's six files — 67 passed; LC-P2-08's
six files — 70 passed; `tests/test_cli_refusal_enumeration.py` and
`tests/test_evaluation_harness.py` — 83 passed. **After** the review, with
every mutation reverted, the fourteen files together — **220 passed, 0
failed**. The tree was clean (`git status --porcelain` empty) before the
first mutation and after the last.

**The result in one line:** **28 PASS, 3 FAIL, 0 INCONCLUSIVE** — 15 PASS /
3 FAIL for LC-P2-06, 13 PASS for LC-P2-08.

**The rule the verdicts follow.** A mutation is a survivor only after the
diff has been read and the change confirmed to be in the tree; a mutation
that did not apply is reported as INCONCLUSIVE, never as a survivor. Every
mutation below was checked with `git diff` before the witness was run, and
the diff is reproduced in the row so a reader can check the same thing.

---

## LC-P2-06 — Data governance, consent and access

| # | The property | The witness | The mutation applied | Verdict |
|---|---|---|---|---|
| 1 | The absence of a row is the refusal | `test_no_grant_is_a_refusal_and_not_an_exception` | `src/labcairn/security/permissions.py:295` — the empty-`candidates` branch returns `allowed=True` | **PASS** — red on `assert decision.allowed is False`; the mutation was applied (`allowed=False` → `allowed=True`) |
| 2 | Permission, purpose, destination and scope are four independent axes | `test_a_grant_for_another_subject_does_not_answer_for_this_one`, `test_a_grant_for_one_destination_does_not_authorise_another`, `test_a_grant_for_another_purpose_is_refused_by_purpose`, `test_a_grant_whose_scope_does_not_reach_the_material_is_refused` | `permissions.py:310` — the `grant.permission == permission` clause is dropped from the covering test | **FAIL** — all four witnesses stayed green, and so did the whole LC-P2-06 consent suite (40 passed). See **F1**. The other three axes were checked separately and are watched: dropping the destination clause turns both destination witnesses red; dropping the subject filter turns six tests red |
| 3 | The owner's identity authorises nothing | `test_the_owner_scope_authorises_nothing` | `permissions.py:292` — the subject filter is dropped **and** the no-grant branch names the owner as a reason | **PASS** — red on `assert "owner" not in decision.detail.lower()`. The subject filter alone turns six tests red, including this one |
| 4 | A withdrawn grant is not a grant that was never made | `test_a_withdrawn_grant_is_refused_as_withdrawn`, `test_a_withdrawal_records_who_and_when` | `permissions.py:313` — withdrawn grants are excluded from the covering set, so they fall through to the "no grant" ranking | **PASS** — red on `assert decision.reason is ConsentRefusal.GRANT_WITHDRAWN`; the detail also loses "Dr. Chen" and "withdrawn". The second witness watches `withdraw_grant`, not `may_use`, and stayed green — it is a witness for the *record*, not for the *reporting* |
| 5 | The withdrawal is not a deletion | `test_the_grant_row_is_kept_and_not_deleted`, `test_a_withdrawn_grant_invalidates_the_copies_derived_from_it`, `test_the_withdrawal_keeps_the_copies_addressable` | `permissions.py:524` — `withdraw_grant` returns the grant unchanged, so the withdrawal leaves no trace on the row | **PASS** — all three red |
| 6 | A copy whose grant is not on the record is stale too | `test_a_copy_whose_grant_is_not_on_the_record_is_stale`, `test_the_stale_copies_are_listed_and_not_a_promise` | `permissions.py:558` — `if grant is None: return False` | **PASS** — both red |
| 7 | The window is both ends | `test_a_grant_that_has_not_opened_yet_is_refused_as_such`, `test_an_expired_grant_is_refused_as_expired` | `permissions.py:150` — the lower bound `if at < self.granted_at: return False` is dropped | **PASS** — the not-yet-active witness red; the expired witness stayed green, as it should, because it watches the other end |
| 8 | An expired grant is reported as expired, not as "no grant" | `test_an_expired_grant_is_refused_as_expired` | `permissions.py:356` — the expiry is found only by `grant.state == "expired"`, so a grant that ran out by the clock falls to the ranking | **PASS** — red on `assert decision.reason is ConsentRefusal.GRANT_EXPIRED` |
| 9 | The transmit gate runs before the approval is consumed | `test_the_transmit_check_runs_before_the_approval_is_consumed`, `test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent` | `src/labcairn/application/model_transmit.py:86` — the gate is given an `approval`/`approval_id` and the approval is consumed **before** `may_use` runs | **FAIL** — the first witness went red (it asserts the gate's parameter set), but the second — the one whose name says *"and the approval is unspent"* — stayed green, because it never mentions an approval. See **F3** |
| 10 | The two gates are two gates | `test_a_read_grant_does_not_authorise_a_transmission`, `test_a_grant_for_one_destination_does_not_authorise_another` | `model_transmit.py:107` — any standing grant for the subject stands in for the transmit grant, so the gates are merged | **PASS** — both red |
| 11 | A refusal names the missing permission and what would satisfy it | `test_a_refusal_names_what_would_satisfy_it` | `permissions.py:437` — the `PURPOSE_NOT_GRANTED` detail becomes `"no"` | **PASS** — red on `assert "grant" in decision.detail` |
| 12 | The schema refuses the rows the design names, and holds no row shape that means "denied" | `test_a_transmit_grant_with_no_destination_is_refused`, `test_a_read_grant_with_a_destination_is_refused`, `test_a_withdrawal_with_nobody_behind_it_is_refused`, `test_a_permission_outside_the_vocabulary_is_refused`, `test_the_table_holds_only_grants_and_therefore_has_no_way_to_say_denied` | four mutations in `migrations/versions/0011_access_grants.py`: (a) drop `access_grants_destination_belongs_to_transmit`; (b) drop `access_grants_withdrawal_names_who_and_when`; (c) widen `access_grants_permission_vocabulary` with `'transmit'`; (d) add a `permitted` column | **PASS** — (a) turns the two destination witnesses red; (b) turns the withdrawal witness red; (c) turns the permission witness red; (d) turns the "no way to say denied" witness red. Each was applied and confirmed by diff before the run |
| 13 | The archive is not opened at all without a grant | `test_material_with_no_grant_is_not_readable`, `test_the_archive_guards_refuse_what_the_design_names` | `src/labcairn/material/intake.py:218` — the grant gate is removed, so the archive is opened first | **PASS** — both red. The failure output shows the mutated result carrying the archive's entries and its compression ratio: the file was read, which is the property |
| 14 | The macro is refused, not cleaned | `test_a_macro_enabled_document_is_refused_not_cleaned`, `test_the_archive_guards_refuse_what_the_design_names` | `intake.py:289` — the macro check is removed entirely | **PASS** — both red |
| 15 | No real material reaches the repository, a CI artefact, or the public evaluation corpus | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` | three mutations: (a) `material_leak.csv` left in the working tree, uncommitted and unignored; (b) `committed_leak.csv` staged on the index (staged, **not** committed); (c) one byte of `tests/fixtures/public/biomedical_panel/panel_readings.csv` changed | **PASS** — (a) red on the working-tree clause; (b) red on the committed-tree clause; (c) red on the manifest hash |
| 16 | Every refusal joins the enumeration the CLI renders | `tests/test_cli_refusal_enumeration.py` (the existing enumeration witness) | `src/labcairn/application/refusal.py:160` — `CONSENT_GRANT_WITHDRAWN` is removed from `ApplicationRefusal` | **FAIL** — the mutation applied, and `test_cli_refusal_enumeration.py` plus the whole LC-P2-06 suite stayed green (75 passed). The two vocabularies drifted apart and nothing noticed. See **F2** |
| 17 | Every test file is in exactly one gate class, and says so itself | `test_the_partition_files_every_test_file_exactly_once`, `test_a_file_that_declares_no_protocol_marker_is_in_no_protocol_class` | two mutations in `tests/evaluation/manifest.py`: (a) remove `test_access_grant_schema.py` from `FILE_ASSIGNMENTS`; (b) re-file `test_intake_guards.py` under `REPOSITORY_CLASS` without changing its own `pytestmark` | **PASS** — (a) red on the partition witness; (b) red on the marker witness (and on `test_the_partition_agrees_with_the_markers_a_file_declares`) |
| 18 | The demonstration runs, and a test runs it | `test_the_consent_demo_runs`, `test_every_step_ran`, `test_the_demonstration_says_the_things_that_matter` | `examples/consent_demo.py:114` — `check(decision.allowed is True, …)` is inverted to `is False` | **PASS** — three of the four demonstration tests red, with the non-zero exit in the traceback. But see **F5**: the fourth (`test_the_demonstration_says_the_things_that_matter`) is hollow |

### The two coordinate systems, checked on their own

The acceptance record names this as the hard case: *"the scope named material
by an absolute path while the subject named a project by its id, and the two
were never in the same system."* The review points do not give it a row of
its own, so it was checked separately.

**Mutation:** `permissions.py:306` — `material = material_ref if material_ref
is not None else subject_ref` becomes `material = subject_ref`, so the scope
is never asked about the material that was named and the two systems are
conflated.

**Result: the property is watched, but by one test and not by the other.**
`test_a_wildcard_scope_does_not_cover_a_sibling`
(`tests/test_dataset_consent.py:352`) goes red. The witness that names the
property — `test_a_grant_whose_scope_does_not_reach_the_material_is_refused`
(`tests/test_dataset_consent.py:315`) — stays **green**, because the scope
`proj-1/drafts/**` does not cover the subject `proj-1` either, so the refusal
is right for the wrong reason. See **F7**.

---

## LC-P2-08 — The paper project and the version graph

| # | The property | The witness | The mutation applied | Verdict |
|---|---|---|---|---|
| 1 | A version graph, never a version list | `test_a_branch_is_representable` | two mutations in `migrations/versions/0010_paper_version_graph.py`: (a) `paper_versions` grows a `NOT NULL` `parent_version_id` with a `UNIQUE` constraint; (b) `version_edges` grows `UNIQUE(parent_version_id)` | **PASS** — (a) red on the first version insert; (b) red on the **second edge insert**, with `UNIQUE constraint failed: version_edges.parent_version_id`, which is the branch itself |
| 2 | Two files, same name and different bytes, are two versions; two with the same bytes are one | `test_two_files_with_the_same_name_and_different_bytes_are_two_versions`, `test_the_same_bytes_are_one_version_whatever_the_name` | two mutations in `src/labcairn/papers/duplicates.py`: (a) the same-label group is never reported, so the name decides and two versions are merged; (b) the content-hash grouping is keyed by the label, so the hash decides nothing and one version is split | **PASS** — (a) red on `assert report.same_label_different_bytes == (("v1","v2"),)`; (b) red on `assert report.same_bytes_different_labels == (("v1","v2"),)` |
| 3 | The order is never taken from a file name or an mtime | `test_a_file_name_never_decides_the_order`, `test_a_modification_time_never_decides_the_order` | two mutations in `src/labcairn/papers/alignment.py`: (a) `VersionFingerprint` grows a `name` field, `fingerprint` gathers it and `propose_alignment` sorts by it; (b) the same with an `mtime` field | **PASS** — both red. Note the shape of the witness: it asserts the *absence* of a field (`assert not hasattr(print_, "name")`), which is the design's stated mechanism — *"a property that cannot be used as evidence should not be gathered"* — and it catches the gathering. It would not catch a name read from outside the fingerprint, and there is no such channel: `propose_alignment` receives text only |
| 4 | A proposal with high confidence is still unaccepted | `test_a_confident_proposal_is_still_unaccepted` | `src/labcairn/papers/versions.py:274` — `is_accepted` becomes `accepted_by is not None or confidence >= 1.0` | **PASS** — red on `assert edge.is_accepted is False`. The schema-level witness `test_a_high_confidence_proposal_is_still_unaccepted` stayed green, which is correct: it asserts the *stored* state, and a model-level mutation does not change what is stored |
| 5 | An edge claiming a human acceptance must name the acceptor; an `evidence` edge may not name one at all | `test_an_edge_with_no_acceptor_is_refused`, `test_a_proposal_wearing_a_persons_name_is_refused` | three mutations: (a) `versions.py:251` — the `source='human'` with no acceptor refusal is removed; (b) `versions.py:257` — the "proposal wearing a person's name" refusal is removed; (c) `0010_paper_version_graph.py` — the schema's `version_edges_acceptance_names_an_acceptor` constraint is dropped | **PASS** — (a) red on `DID NOT RAISE ValidationError`; (b) red on `DID NOT RAISE ValidationError`; (c) red on `DID NOT RAISE IntegrityError` |
| 6 | The alignment refuses to decide when the evidence points two ways | `test_the_alignment_refuses_when_the_evidence_points_two_ways` | `alignment.py:365` — the ambiguity margin becomes `margin < 0.0`, so a near-tie always decides | **PASS** — red on `assert proposal.decided is False` |
| 7 | Two drafts whose prose matches and whose numbers differ are two versions | `test_two_drafts_that_differ_only_in_their_results_are_two_versions` | `alignment.py:147` — the fingerprint collects no numbers | **PASS** — red on `assert numbers` (and `test_the_number_signal_is_not_optional` red on `assert "3.14159" in print_.numbers`) |
| 8 | A missing round is reported, and no version is invented to fill it | `test_a_missing_round_is_reported_and_nothing_is_invented` | `duplicates.py:218` — the gap is renumbered away (`missing = ()`) | **PASS** — red on `assert report.missing == (3,)` |
| 9 | A correction is a new version of the edge, and the old one stays readable | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` | `versions.py:456` — the correction reuses the proposal's `edge_id` and the proposal is not marked as superseded | **PASS** — red on `assert decision.edge.edge_id != proposal.edge_id` |
| 10 | An edge whose parent is outside the project is refused | `test_an_edge_to_a_version_outside_the_project_is_refused` | `versions.py:519` — the cross-project check is disabled | **PASS** — red on `DID NOT RAISE ValueError`. This is the rule a CHECK constraint cannot hold — a fact about three rows — and the model holds it |
| 11 | A version with no established parent is `unresolved`, and it is listed | `test_a_version_with_no_established_parent_is_unresolved_and_listed` | two mutations: (a) `versions.py:176` — the default becomes `VersionStatus.RESOLVED`; (b) `0010_paper_version_graph.py` — the schema's status constraint becomes `status = 'resolved'`, so an unresolved version cannot be stored | **PASS** — (a) red on `assert version.status is VersionStatus.UNRESOLVED`; (b) red on `CHECK constraint failed` for `test_an_unresolved_version_is_storable` |
| 12 | A rejection writes no edge and keeps the proposal | `test_a_rejection_writes_no_edge_and_keeps_the_proposal` | `versions.py:414` — the proposal a rejection was about is discarded (`corrects=None`) | **PASS** — red on `assert decision.corrects is not None` |
| 13 | The demonstration runs, and a test runs it | `test_the_paper_version_demo_runs` | `examples/paper_version_demo.py:213` — `check(proposal.decided, …)` is inverted | **PASS** — all five of the file's tests red, the exit code carrying the failure |

---

## Findings

Ordered by severity. Each names the file and line, the concrete failure
scenario, and the smallest change that would fix it.

### F1 — High. The permission axis is not watched

**Where:** `src/labcairn/security/permissions.py:310` (the covering test's
`grant.permission == permission` clause), and the four witnesses the review
points name for row 2.

**Failure scenario.** Drop the clause. A grant of `store_read` for the purpose
`read` then answers for a `train_reuse` use: measured on the mutated tree,
`may_use([read_grant], permission="train_reuse", purpose="read",
material_ref="proj-1/drafts/v1.docx")` returns `allowed=True, grant_id="g1"` —
a training use authorised by a read grant. The shipped tree refuses the same
input with `reason=no_grant`. **All four named witnesses stayed green, and so
did the entire LC-P2-06 consent suite (40 tests).** The reason is that in
every case the suite constructs, the *purpose* already excludes the grant, so
the permission clause is never the binding constraint. The three other axes
are watched (destination: 2 tests red; purpose: the purpose witness red;
scope: the scope witness red) — the gap is exactly one axis wide.

**Smallest fix.** One witness that holds the purpose fixed and changes the
permission: a `store_read`/`read` grant, asked for `train_reuse`/`read`,
asserting `allowed is False` and `reason is ConsentRefusal.NO_GRANT`. That
is one test, and it is the case the missing clause decides.

### F2 — High. The consent and intake refusals never reach the CLI, and the two vocabularies have already drifted

**Where:** `src/labcairn/application/refusal.py:146-181` (the seven
`CONSENT_*` and five `INTAKE_*` members), `src/labcairn/material/intake.py:57`
(`IntakeRefusal.NO_GRANT`), and `tests/test_cli_refusal_enumeration.py`
(which has no knowledge of `ApplicationRefusal` at all).

**Failure scenario.** A refusal produced by the consent machinery is a field
on a dataclass: `ConsentDecision.reason` is a `ConsentRefusal`. Nothing maps
it to an `ApplicationRefusal`, and nothing raises an
`ApplicationRefusedError`. So no surface can print it: the CLI's
`emit_refusal` and the API's error body both render
`ApplicationRefusedError.to_payload()`, and a consent refusal never becomes
one. A caller branching on the machine-readable reason sees no
`consent_grant_withdrawn` value, because the value exists only in an enum
that nothing reaches. **The twelve members this work order added to
`ApplicationRefusal` are dead vocabulary**: a grep of `src/` and `tests/`
finds their strings in `refusal.py` and nowhere else — no code raises them,
no test names them, and removing one leaves `test_cli_refusal_enumeration.py`
and the whole LC-P2-06 suite green (75 passed, measured).

The drift is already present in the shipped tree: **`IntakeRefusal` has six
members and `ApplicationRefusal` has five `INTAKE_*` counterparts.** The
missing one is `NO_GRANT` — the intake's own "no grant" refusal, which is the
first thing the module refuses with (`intake.py:218`) — has no name in the
layer's vocabulary at all.

**Smallest fix.** The project already has the pattern: `ANALYSIS_REFUSALS` in
`src/labcairn/application/analysis.py:67` maps a run path's vocabulary onto
`ApplicationRefusal`, and `tests/test_analysis_service.py:1686`
(`test_every_run_path_refusal_has_a_layer_name`) closes the two vocabularies
against each other. A `CONSENT_REFUSALS` / `INTAKE_REFUSALS` mapping plus a
witness of that shape — "every reason in `ConsentRefusal` and `IntakeRefusal`
has a name in `ApplicationRefusal`, and every name in it is reachable" — would
close the row-16 property and catch the missing `NO_GRANT` at the same time.
The `INTAKE_NO_GRANT` member has to be added.

### F3 — High. "The approval is unspent" is witnessed by nothing

**Where:** `tests/test_consent_two_gates.py:96` (the witness named
`…_and_the_approval_is_unspent`), `examples/consent_demo.py:134` (the
sentence it prints), `tests/test_consent_demo.py:101` (the assertion on that
sentence).

**Failure scenario.** The witness's body is:

```python
    check = check_transmit(
        [],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "no_grant"
    assert "remedy" in check.detail
```

There is no approval in it. There is no approval in the demonstration either:
step 2 *prints* "The operation approval was never consumed: asking is not
spending." unconditionally, with no approval object and no check behind it,
and `test_the_demonstration_says_the_things_that_matter` asserts that literal
string. **Deleting every `check()` in the demonstration's step 2 leaves all
four of `tests/test_consent_demo.py`'s tests green** (measured). And
`src/labcairn/application/model_transmit.py` is called from **no production
code at all** — only from `examples/consent_demo.py` and its own test — so
there is no path on which an approval could be spent before the gate.

The consequence is a claim that is true of the code and false of the product:
ADR-0015's contract C2 reads *"the refusal does not spend the operation
approval"*, and the acceptance record's A6 reads *"a request with no transmit
grant is refused and the approval is not spent"*. What the tree actually
holds is a gate that takes no approval — a weaker and, for a reader of the
record, indistinguishable claim. When LC-P2-01 wires a real model request,
the ordering that has to hold is unwatched, and the record has already
announced that it holds.

**Smallest fix.** Two honest options. (a) Wire an approval into the transmit
path and witness the order: a request refused for a missing grant must leave
the approval spendable, asserted against the real approval ledger. (b) If
the ordering is LC-P2-01's to witness, rename the witness and the printed
sentence to what is true — *"the transmit gate takes no approval and spends
nothing"* — and amend ADR-0015's C2 to say the ordering against the operation
approval is unwitnessed until then. (a) is better; (b) is smaller.

### F4 — Medium. A grant whose window has closed leaves its derived copies live

**Where:** `src/labcairn/security/permissions.py:541-560`
(`is_copy_stale`) and `:563` (`stale_copies`); the witness at
`tests/test_consent_withdrawal.py:200`.

**Failure scenario.** A grant with `expires_at` in the past and
`state='active'` — which is what every real expiry looks like, because
**nothing in the product ever writes `state='expired'`** on an access grant
(`src/labcairn/db/models.py:1677` is only the vocabulary constraint) — is
refused by `may_use` with `grant_expired`, and yet its derived copy is
reported fresh. Measured on the shipped tree:

```
may_use       -> allowed=False reason=grant_expired
is_copy_stale -> False
stale_copies  -> ()
```

`is_copy_stale` takes no clock at all and reads only the state column, so
the `state in ("withdrawn", "expired")` branch is dead in the product and the
expiry half of the propagation never fires. The direction of the error is
the one the module's own docstring calls out as wrong: *"treating 'I cannot
find the grant' as 'the grant is fine' would be the wrong direction of
error."* Here it is "the grant has run out" treated as "the grant is fine".

The witness `test_an_expired_grant_also_makes_its_copies_stale` gives the
impression this is covered. It is not: it builds the expired grant by
setting `state="expired"` **by hand**, which is a state the product never
writes.

**Smallest fix.** Give `is_copy_stale` and `stale_copies` an `at` parameter
and ask `Grant.is_in_force(at)` — which already tests both ends of the
window — instead of reading the state column. Then change the witness to
build an expired grant from an `expires_at` in the past with `state="active"`,
which is the case that is actually reachable.

### F5 — Medium. LC-P2-06's demonstration has no guard-count witness

**Where:** `tests/test_consent_demo.py` (the whole file — four tests, none of
them counting guards), against `tests/test_paper_version_demo.py:137`
(`test_the_demonstrations_guards_are_guards`), which LC-P2-08 has and
LC-P2-06 does not.

**Failure scenario.** Delete every `check()` in the demonstration's step 2.
The demonstration still prints its five steps, still prints the reason and the
remedy and the claim about the approval, and still exits zero — and **all
four of `tests/test_consent_demo.py`'s tests stay green** (measured). A
missing assertion is invisible to an exit code, and LC-P2-06's demonstration
has no second witness that counts the assertions. The two work orders
shipped the same kind of demonstration; only one of them can notice a
hollowed-out step, and the LC-P2-06 acceptance record does not mention the
difference.

**Smallest fix.** Port the guard-count witness from
`tests/test_paper_version_demo.py:137-174` into `tests/test_consent_demo.py`,
with the floor read off `examples/consent_demo.py`. The LC-P2-08 witness
already states the limit honestly — *"it does not catch the removal of a
single guard, because a count with a floor is not an identity"* — so the same
wording should come with it.

### F6 — Low. "There is no row shape that means denied" is a five-name blacklist

**Where:** `tests/test_access_grant_schema.py:297`.

**Failure scenario.** `forbidden = {"permitted", "allowed", "denied",
"granted", "is_permitted"}`. A grant table that grew a column named
`consent_state`, or `permitted_flag`, or one whose `state` could hold
`'denied'`, would pass this witness and would break ADR-0015 D2's rule
(*"There is no row, so there is nothing to check"*) — a flag column is
precisely what D2 says must not exist. The witness as written catches the
five spellings a reader would guess, and nothing else. (The mutation in row
12(d) — a column named `permitted` — is caught, which is why the row passes;
the row's property is stronger than its witness.)

**Smallest fix.** Assert the shape rather than a name list: every column of
`access_grants` is one of the columns ADR-0015 D1 names, and `state`'s
vocabulary is exactly `('active', 'withdrawn', 'expired')` — the second is
already enforced by the schema, so the first is the part to add.

### F7 — Low. The scope witness passes for the wrong reason under a coordinate-system mix-up

**Where:** `tests/test_dataset_consent.py:315`
(`test_a_grant_whose_scope_does_not_reach_the_material_is_refused`), against
`:352` (`test_a_wildcard_scope_does_not_cover_a_sibling`).

**Failure scenario.** Conflate the two coordinate systems — set
`material = subject_ref` at `src/labcairn/security/permissions.py:306`, so the
scope is never asked about the material that was named. The witness that
names the property stays **green**: the scope `proj-1/drafts/**` does not
cover the subject `proj-1` either, so the refusal is right but the reason is
not the one the witness names. Only the sibling witness catches it. The
scope axis therefore has one real witness and one incidental one, and the
incidental one is the one whose name matches the property.

**Smallest fix.** Give the scope witness a grant whose scope *does* cover the
subject but not the material named — scope `proj-1/**` with
`material_ref="proj-1-secrets/x.docx"`, which the wildcard does not reach but
which is inside the subject's project — and assert
`reason is ConsentRefusal.SCOPE_NOT_COVERED`. Under the mix-up that grant
would be allowed, and the witness would go red.

---

## Closing statement

**I wrote none of the fixes.** Every finding above is a description of what is
wrong and what would make it right; no defect was repaired, and the tree at
`ff93b1d` is exactly as it was found. Nothing was committed and nothing was
pushed; the only file this review added is this report.

**What was changed temporarily, and restored.** Every mutation below was
applied with an editor or a shell command, was confirmed by `git diff` before
its witness was run, and was reverted with `git checkout --` (or, for the
staged file, `git reset` plus deletion) immediately afterwards.

| File | Rows it was mutated for | Restored |
|---|---|---|
| `src/labcairn/security/permissions.py` | 1, 2, 3, 4, 5, 6, 7, 8, coordinate systems | yes |
| `src/labcairn/application/model_transmit.py` | 9, 10 | yes |
| `src/labcairn/application/refusal.py` | 16 | yes |
| `src/labcairn/material/intake.py` | 13, 14 | yes |
| `migrations/versions/0011_access_grants.py` | 12(a)–(d) | yes |
| `migrations/versions/0010_paper_version_graph.py` | 1, 5(c), 11(b) | yes |
| `src/labcairn/papers/duplicates.py` | 2(a), 2(b), 8 | yes |
| `src/labcairn/papers/alignment.py` | 3(a), 3(b), 6, 7 | yes |
| `src/labcairn/papers/versions.py` | 4, 5(a), 5(b), 9, 10, 11(a), 12 | yes |
| `examples/consent_demo.py` | 18, and the step-2 checks deleted for F5 | yes |
| `examples/paper_version_demo.py` | 13 | yes |
| `tests/evaluation/manifest.py` | 17(a), 17(b) | yes |
| `tests/fixtures/public/biomedical_panel/panel_readings.csv` | 15(c) — one byte | yes |
| `material_leak.csv` (created) | 15(a) | deleted |
| `committed_leak.csv` (created) | 15(b) — staged, never committed | unstaged and deleted |

**The tree's final state:** `git status --porcelain` empty; the fourteen
reviewed test files — 220 passed, 0 failed.

**What a reader should take from the three FAILs.** Two of them (F1, F3) are
properties that are true of the code and unwatched, which is the failure the
project's own rule names: *"a property that is stated and not watched is not
held."* The third (F2) is a vocabulary that exists on paper and reaches
nobody. None of the three is a defect in the shipped behaviour that a user
would hit today; all three are places where the acceptance record's wording
runs ahead of what the tree will catch if the behaviour changes. **F1 is the
one to look at first**, because it is the check the whole work order exists
for and the one axis of it that nothing holds.
