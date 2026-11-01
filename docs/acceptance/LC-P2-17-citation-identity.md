# LC-P2-17 — Citation identity and support

**Work order:** the merged work order's item 4 (`docs/plans/PHASE_2-work-orders.md` §3 row 4)
**Builds the half of:** LC-P1-09's acceptance clause its review named as
structurally missing — *"no record can carry an identifier, nothing resolves
one, and ingestion records none"*
**Branch:** `claude/charming-jones-03cf91` (this worktree; the coordinator merges)
**Date:** 2026-11-02
**Scope of this record:** the design, the five clauses with their witnesses,
the mutation table, and what was deliberately not done.

## What the gap was

LC-P1-09's acceptance review (Clause 2 — fabricated DOI/source) discharged the
fabricated **source** and left the fabricated **DOI** undischarged, and named
the reason structural rather than an oversight: `EvidenceRecord` carried
`anchor_ids` and no identifier field, no table held a DOI, nothing resolved
one, and ingestion recorded none. Reports cite locators only — which is
ADR-0004's contract, not a shortcut — but a claim whose support names a DOI
had nowhere to put the DOI and no way to say whether anyone had resolved it.

## The design

### Three closed vocabularies (`src/labcairn/evidence/identifiers.py`)

| Vocabulary | Members | Why these |
|---|---|---|
| `IdentifierScheme` | `doi`, `arxiv` | the two the work order names; a third would be a guess at what a future resolver wants |
| `IdentifierProvenance` | `ingestion`, `person`, `model` | who supplied it — and the third member is the one the work order is about |
| `ResolutionState` | `unresolved`, `not_attempted`, `resolved` | resolution is **a state, not a failure** |

**Resolution is a state machine, one-way.** `unresolved → not_attempted |
resolved`; `not_attempted → resolved`; `resolved` is terminal. A resolution
is a statement about the world that other readers may have acted on, so it is
not unwritten — a correction is a new confirmation with its own detail, and
the store refuses to overwrite one.

**A resolution state carries the evidence of what it names.** The same
discipline as a record's `unit`: declared, never inferred. `unresolved`
carries none of the three fields, because nothing has happened;
`not_attempted` carries the reason it did not happen and nothing else, so a
resolver's name cannot ride on a lookup that never ran; `resolved` carries
who answered, what they found and when. Enforced twice — in the Pydantic
model and in three CHECK constraints — because the store is a boundary, and
a row written by a SQL client skips the model.

### The two axes are deliberately separate

An identifier's **resolution** and a record's **verification** are different
questions. `ResolutionState` has no "verified" member and
`VERIFICATION_STATES` has no "resolved" member — a witnessed structural fact
(`test_the_resolution_and_verification_vocabularies_share_no_words`), not a
convention. Nothing that happens to an identifier writes to a record's
`verification_log` or moves a record's status, and the functions that change
a resolution state take no record id and return identifiers only: there is no
parameter a record id could hide in.

### The outbound boundary (ADR-0006), respected by construction

Resolving a scholarly identifier means contacting an external service. This
build cannot consent an outbound lookup: the closed capability registry
(`security.capabilities.CapabilityId`) defines exactly one network-effect
capability, `model.request`, which is consent to prompt a provider and
consent to nothing else, and the bridge ADR-0006 describes between the two
capability vocabularies is unbuilt.

So the design records a resolution request as **`not_attempted`** rather than
silently sending it or silently dropping it. `request_resolution` (and the
product path `request_outbound_resolution`) has no parameter that could hold
a response and no code path that leaves the identifiers' own tables; the row
carries the caller's reason *and* the boundary's own reason appended to it,
so the reader finds the rule and not merely the caller's wish. **A future
resolver must arrive through the consent layer with a capability that exists
in the closed registry**; until then, `not_attempted` is the truthful state
of the world, queryable and reported like any other.

The honest path is guarded at runtime, not by an intention: the witness runs
the request with `socket.socket`, `socket.create_connection` and
`urllib.request.urlopen` monkeypatched to raise, so "nothing reached the
network" is measured (mutation M9).

### The two refusals that carry LC-P1-09's rule

**A claim may not rest on an identifier nothing resolved.** The rule is
enforced at two doors, on purpose:

1. **The store** (`evidence.store._require_supported_identifiers`, called
   from `append_record`, `advance` and `attest`): a record whose status is
   citeable (`verified_by_rule`, `user_attested` — the one set
   `states.CITABLE_STATUSES`, now defined beside the six states both readers
   live off) may not cite an identifier whose state is not `resolved`. The
   refusal names the identifier and its state. A record in any other state
   may cite any state of identifier — a `planned` proposal carrying a model's
   DOI is data, and refusing it would refuse the provenance the work order
   exists to record. The store also refuses an unknown identifier and one
   belonging to another task, wherever the record is written or moved.
2. **The gate** (`evidence.gate._judge_identifiers`): a citeable record
   resting on a non-`resolved` identifier produces an
   `unresolved_identifier` finding that names the identifier, its state and
   its provenance. The store refuses such a record at write time, so a
   finding here means the write went around the store — and the gate is the
   door such a writer has not passed.

### Proposing is not checking

`IdentifierProvenance.MODEL` exists so the attribution is readable, and
nothing else. The application's `confirm_identifier_resolution` is the only
door to `resolved` and takes no evidence-record id; the store-level
`confirm_resolution` likewise touches identifiers and nothing else. Witnessed
by `test_confirming_a_models_proposal_writes_no_check_and_moves_no_status`,
which asserts the record is **byte-identical** (`model_dump_json`) across a
person's confirmation of a model's proposal — and by
`test_a_verified_record_still_needs_its_checks_beside_a_resolved_identifier`,
which shows a resolved identifier does not stand in for a passing check
entry.

## What was built, and where

| File | Change |
|---|---|
| `src/labcairn/evidence/identifiers.py` | **new** — the vocabularies, `ScholarlyIdentifier`, and the store functions (`put_identifier`, `load_identifier`, `load_task_identifiers`, `request_resolution`, `confirm_resolution`) |
| `migrations/versions/0021_identifier_records.py` | **new** — direct DDL, chained from 0020; `identifier_records` (with the three state rules, the unique triple) and `evidence_identifiers` (the join, no FK by the A12 reasoning `evidence_anchors` records) |
| `src/labcairn/db/models.py` | `IdentifierRow`, `EvidenceIdentifierRow`, with the same CHECK texts (one per state rule, vocabulary via `sql_string_list`) |
| `src/labcairn/evidence/record.py` | `EvidenceRecord.identifier_ids` (ids, not embedded objects; order meaningful; duplicates refused) |
| `src/labcairn/evidence/store.py` | `_require_supported_identifiers`, wired at `append_record`/`advance`/`attest`; the join rows written and read back |
| `src/labcairn/evidence/states.py` | `CITABLE_STATUSES` moved here (it is a property of the six states, and two modules read it); `gate` re-imports it |
| `src/labcairn/evidence/gate.py` | `_judge_identifiers`, the `unresolved_identifier` finding |
| `src/labcairn/application/identifiers.py` | **new** — `record_identifier`, `request_outbound_resolution`, `confirm_identifier_resolution`, `list_task_identifiers`; capability asked per operation, the signature and ownership rules |
| `src/labcairn/application/refusal.py` | `IDENTIFIER_NOT_FOUND`, `RESOLUTION_IDENTITY_EMPTY` |
| `src/labcairn/application/__init__.py` | the new operations exported, and the docstring's capability table rows for all four |
| `tests/test_application_layer.py` | `labcairn.application.identifiers` recorded in `_ALLOWED_STORE_READERS`, with its reason |
| `web/src/api/generated.ts` | regenerated from the models this work changed (`EvidenceRecord.identifier_ids`) — a mechanical derivative, not a hand edit |
| `tests/test_identifier_records.py` | **new** — 35 tests, `pytestmark = pytest.mark.integration` |
| `tests/test_store_migrations.py` | the two new tables in `EXPECTED_TABLES` (the hand-listed set) |

## The mutation table

Every witness was reddened by a mutation that breaks its property and the
mutation reverted byte-for-byte (`git checkout --` after each, with the work
committed first). **No mutation survived.**

| # | Mutation (applied, then reverted) | Witness that reddened | Result |
|---|---|---|---|
| M1 | the identifier check deleted from `advance` | `test_a_verified_record_cannot_rest_on_an_unresolved_identifier` | red |
| M2 | the identifier check deleted from `append_record` | `..._nobody_recorded_is_refused`, `..._another_tasks_identifier_is_refused` | 2 red |
| M3 | the identifier check deleted from `attest` | `test_an_attested_record_cannot_rest_on_an_unresolved_identifier` | red |
| M4 | `_judge_identifiers` dropped from `evaluate_task` | `test_the_gate_names_an_identifier_a_citable_record_rests_on` | red |
| M5 | `request_resolution` writes `resolved` instead of `not_attempted` | the two `not_attempted` witnesses | 2 red |
| M6 | `confirm_resolution` injected with a `verification_records` INSERT (the "a resolution is a check" inflation) | `test_confirming_a_models_proposal_writes_no_check_and_moves_no_status` (byte-identical log) | red |
| M7 | the `identifier_resolved_says_who` CHECK deleted from the migration | `test_a_resolved_row_without_its_evidence_is_not_storable` **and** the ORM/migration parity test | 2 red |
| M8 | the `_state_carries_what_it_names` validator deleted | `test_a_state_disagreeing_with_its_fields_is_refused_at_construction` | red |
| M9 | a real `urllib.request.urlopen` call injected into `request_resolution` | the socket-guard witness (`test_a_resolution_request_is_recorded_not_attempted_and_not_sent`) | red |
| M10 | the gate's resolved-skip disabled (`if True: continue`) | `test_the_gate_names_an_identifier_a_citable_record_rests_on` | red |
| M11 | the store's `is not RESOLVED` flipped to `is RESOLVED` | `..._cannot_rest_on_an_unresolved...` **and** `..._may_rest_on_a_resolved...` | 2 red |
| M12 | the confirmation's identity check disabled | `test_an_unsigned_confirmation_is_refused` | red |
| M13 | the ownership check disabled | `test_another_tasks_identifier_is_not_resolved_here` | red |
| M14 | the boundary reason reduced to `""` | both `not_attempted` witnesses (the detail assertion) | 2 red |

**One honest note on M9.** The first attempt injected the network call into
`confirm_resolution` instead of `request_resolution` — the mutation never
took effect on the tested path, and the suite stayed green. That was **not a
survivor**; it was a mutation aimed at the wrong line (the two functions
share a `load_identifier` line and the first attempt picked the wrong
occurrence). Re-aimed at `request_resolution`, the socket guard reddened at
once. It is recorded because the task's discipline says to say which mutations
survived and why: none survived, and the one that appeared to was misplaced.

## What was deliberately not done

* **No resolver.** Nothing opens a socket, and no capability for scholarly
  lookup exists in the closed registry. The outbound bridge is ADR-0006's
  known Phase-1 debt; when it is built, `request_outbound_resolution` is the
  seam it plugs into — through the consent layer.
* **No CLI/API surface.** `cli/` and `api/` are outside this work order's
  file map; the application-layer operations are the wiring point.
* **No workbench rendering.** `web/` is out of scope by the file map; a
  verification-state display is a follow-up for whoever owns `web/**`.
  `list_task_identifiers` returns everything a display needs.
* **No automatic identifier extraction during ingestion.** The ingestion
  path can *record* identifiers (`supplied_by="ingestion"`) once a reader
  produces them; extracting DOIs from document bytes belongs to
  `material/**`, which is outside this work order's map.
* **No report template change.** `reports/` is outside the map; the gate's
  finding and `list_task_identifiers` are what a report layer reads.

## Measurement status

* `ruff check .`, `ruff format --check .`: clean (409 files).
* `mypy --strict src/labcairn tests/test_application_layer.py`: clean (193
  source files); the README's own `uv run mypy` check: 371 files, clean.
* New and neighbouring evidence tests: 35 new, 225 total across the seven
  evidence/store/migration files — all green.
* **The full suite** (with `PYTHONPATH` pointing at this worktree's `src`,
  clean-room files excluded): 4477 passed, 7 failed. **Four of the seven were
  this work's own drift, all fixed and green on the same tree:**
  1. `test_the_capability_table_covers_every_operation_the_layer_exports` —
     the four new operations were missing from the layer's docstring table.
     Added.
  2. `test_no_module_outside_the_layer_reaches_past_it` —
     `labcairn.application.identifiers` reaches the store, so it is recorded
     in the witness's `_ALLOWED_STORE_READERS` with its reason, as
     LC-P2-09's `papers` was before it.
  3. `test_the_checked_in_typescript_is_what_the_python_models_produce` —
     `EvidenceRecord.identifier_ids` was missing from
     `web/src/api/generated.ts`. Regenerated with the command the failure
     names (`python -m labcairn.api.typescript`), pointed at this worktree's
     `src`. The generated file is a mechanical derivative of the models this
     work changed, so it moved with them; `web/**` is otherwise untouched,
     and the main checkout's `web/` had no uncommitted work to collide with.
  4. `test_wheel_installs_clean_and_imports` — **not a code failure.** The
     `PYTHONPATH` set for the suite run leaks into the throwaway venv's
     subprocess and shadows the installed wheel with the source tree. Run
     without it (the test builds its wheel from this worktree's `repo_root`,
     so migration 0021's packaging is what the green run exercised), it
     passes.
  **The remaining two** are `test_ci_shard_coverage.py`'s shard-coverage and
  recorded-cost witnesses: `tests/test_identifier_records.py` is a new test
  file in no shard yet, so they are red on purpose. Adding it needs
  runner-measured costs (`python .github/remeasure_shards.py` from a CI
  run's log), which a development machine cannot supply — the repository's
  own rule.
* The two clean-room files (`test_readme_accuracy.py`,
  `test_outsider_path.py`), run without `PYTHONPATH` per the repository's
  rule: **41 passed** on this worktree's final tree — the same number the
  main checkout gives.
