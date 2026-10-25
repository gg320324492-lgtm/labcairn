# The P1 review dossier — upstream designs, LabCairn's independent implementation, and its tests

**Work order:** LC-P1-14 (public alpha handoff and review dossier) · **Task:** T08
**Status:** the dossier exists; the checkbox it discharges is `docs/UPSTREAM_REFERENCES.md:187`.
**Tree it describes:** `dd08573` — the merge of the first four G5 components into the delivery branch. Every claim below is about the tree at that commit.
**Measured:** 2026-10-25.

**What this document is for.** One external reviewer, with no access to any upstream
repository, has to be able to answer one question: **of the things LabCairn does,
which are LabCairn's own work, and which are somebody else's?** This document is
the answer, and the answer is that the *ideas* were studied and the *code* was
written here. It says which upstream designs informed which LabCairn decision,
what was refused and why, and which test witnesses each LabCairn behaviour so the
reader can check the claim rather than believe it.

**What this document is not.** It is not a comparison, and it contains no claim that
LabCairn is better than any upstream project. `docs/EVALUATION.md:29` forbids
claiming superiority over PaperQA2/PaperSpine/others without like-for-like
matched-task baselines, verified capabilities, and documented confidence intervals
or limitations, and `docs/UPSTREAM_REFERENCES.md:127` forbids claiming superiority
from source-code inspection alone. **No such baseline was run, so no ranking is
printed.** §7 lists what would be needed to make one.

---

## 0. How to read it

### 0.1 Three words, used precisely

| Word | What it means here | How a reviewer tells them apart |
|---|---|---|
| **Studied** | An upstream repository was cloned, read at a pinned commit, and an observation was recorded. **Nothing of it is in LabCairn.** | The observation lives in an ADR under "Upstream evidence (reference only)", and the upstream file path is named there. |
| **Referenced** | An upstream *design idea* informed a LabCairn contract. LabCairn's contract has its own vocabulary, its own types, its own file layout and its own tests. **No upstream source is present in the tree.** | The LabCairn side names a file under `src/labcairn/` and a test function. The upstream side names a path in the ADR. |
| **Reused** | Upstream source code is present in the LabCairn tree, in whole or in part. | **There is none.** §4 measures this and says how. |

There is a fourth state that is neither of these and that a reviewer is entitled to
know about, so it is named here rather than left implicit: **pydantic-ai is an
installed library dependency.** LabCairn depends on it from PyPI, resolves it in
`uv.lock`, and calls it from three modules inside
`src/labcairn/providers/`. That is ordinary use of a dependency, not reuse of
source: no upstream file was copied into this repository. §4.3 states the tier
precisely, because a document that says "no code was reused" while a reader can
find `from pydantic_ai.messages import ...` in the source is a document that has
been caught out.

### 0.2 The rules this document obeys

1. **Every upstream claim carries an anchor.** A statement about upstream is
   written as `docs/UPSTREAM_REFERENCES.md:NN`. The line numbers are the
   current ones as of the tree named above: they are an index, not a hash, and
   the anchored passage's own wording is quoted wherever the claim turns on it,
   so a reader can repair a shifted number by reading the record itself.
2. **No upstream file content is reproduced here.** The dossier names the upstream
   *path* and the *conclusion of the observation* made at that path, and points at
   the ADR that records it. The upstream source trees are not in this repository
   and their contents are not quoted into it. §6 explains why that is a security
   property and not only a bookkeeping one.
3. **Every LabCairn behaviour claim names its witness.** A behaviour without a
   test function is stated as a limit, not as a fact. §5 is the index.
4. **A number that can change is measured here, and dated.** The counts in §4.2
   and §5.3 were measured on 2026-10-25 on the tree named at the top of this
   document, and the method is stated with them.

---

## 1. The upstream study

### 1.1 The five cloned repositories

All five were cloned as shallow single-branch snapshots on **2026-10-15**
(`docs/UPSTREAM_REFERENCES.md:32`). The SHA column was read from each local
object store rather than resolved from the remote, so a fresh `git clone` of a
default branch does not necessarily reproduce it
(`docs/UPSTREAM_REFERENCES.md:32`); all five were resolved against GitHub at the
LC-P1-00 review and found present upstream
(`docs/UPSTREAM_REFERENCES.md:34`). **The local snapshot is not permanent and
neither is upstream's retention of the commit** — the honest statement is
two-sided, and it is the one this dossier repeats rather than improves on.

| # | Repository | URL | Commit SHA | Licence at that revision | Study areas |
|---|---|---|---|---|---|
| 1 | `pydantic-ai` | https://github.com/pydantic/pydantic-ai | `9ac853bb84ffed7ba0edccb026c5b4f3228c1de7` | MIT | typed tools, model adapters, tests, streaming |
| 2 | `openhands-sdk` | https://github.com/OpenHands/software-agent-sdk | `8efff8d3cf1a5a3fcf7ce5e3b97c7f00684d9547` | MIT | events, tools, execution environment, SDK seams |
| 3 | `deepagents` | https://github.com/langchain-ai/deepagents | `825acb3ca03bd103e4df6013b122eca8475d1982` | MIT | context boundaries, subagent delegation, tool-surface permissions (filesystem-only), skill composition |
| 4 | `paper-qa` | https://github.com/Future-House/paper-qa | `57e89f7223b0960d5ee5ea048c69e3c47e088572` | **Apache-2.0 at the root; AGPL-3.0 in `packages/paper-qa-pymupdf/`** | scientific retrieval, excerpts, citation/provenance |
| 5 | `paperspine` | https://github.com/WUBING2023/PaperSpine | `42312b8d9c76ab25990cddfd76e3622276854118` | MIT | evidence, research flow, review, deliverables |

*Source for the whole table: `docs/UPSTREAM_REFERENCES.md:38`–`:48`. The licences
were not read from repository metadata but by opening each `LICENSE` file at the
pinned commit (`docs/UPSTREAM_REFERENCES.md:30`), and subdirectories were walked
separately from the root (`docs/UPSTREAM_REFERENCES.md:54`).*

**The licences in that table are not a legal assessment**, and transitive
dependencies may carry other licences — the catalog says so itself
(`docs/UPSTREAM_REFERENCES.md:30`).

### 1.2 The four that were not cloned

`opencode`, `gpt-researcher`, `storm` and `ai-scientist-v2` were catalogued but
never cloned (`docs/UPSTREAM_REFERENCES.md:45`–`:48`). **No SHA is recorded for
them on purpose**: an invented or guessed SHA is worse than a blank, because it
looks verifiable (`docs/UPSTREAM_REFERENCES.md:50`). They therefore contributed
**no observation and no design** to anything in LabCairn, and nothing in this
dossier is derived from them.

Two further cautions recorded at study time apply to any future use: OpenHands'
former `All-Hands-AI/OpenHands` address is not the recommended SDK checkout, and
OpenCode uses a different core language stack, so its contracts would have to be
studied rather than ported; AI Scientist v2's licence carries explicit
restrictions and an AI-generated-scientific-manuscript disclosure condition
(`docs/UPSTREAM_REFERENCES.md:87`).

### 1.3 The licence boundaries, including the one that mattered

Every `LICENSE` file in each cloned tree was opened at the pinned SHA
(`docs/UPSTREAM_REFERENCES.md:54`). Three of the five clones have subdirectories
that carry a different licence, a different attribution, or a different shape
entirely — "**a GitHub repository-level license badge is a root-directory
statement, and a root statement is not a repository statement**"
(`docs/UPSTREAM_REFERENCES.md:56`).

| Clone | `LICENSE` files found | What they actually say (`docs/UPSTREAM_REFERENCES.md:58`–`:64`) |
|---|---|---|
| `pydantic-ai` | 8 | All MIT. No conflict. |
| `openhands-sdk` | 3 | Root MIT plus two subdirectory MIT files; one is a test-fixture stub with no named holder. All permissive. |
| `deepagents` | 14 | Root and `libs/*` MIT; two vendored benchmark copies are Apache-2.0; one file is a self-written attribution header over the MIT text. **No copyleft anywhere.** |
| `paper-qa` | 5 | **The important finding** — see below. |
| `paperspine` | 1 | Single root MIT. No subdirectory licences, because there are no subpackages. |

**The `paper-qa` finding, which is the one a licence review must not miss.** The
root `LICENSE` and the licences of `paper-qa-docling`, `paper-qa-nemotron` and
`paper-qa-pypdf` are Apache-2.0, but
**`packages/paper-qa-pymupdf/LICENSE` is the GNU Affero General Public License
v3** (`docs/UPSTREAM_REFERENCES.md:68`). It is not a stray file: the subpackage's
own `pyproject.toml` declares `license = {file = "LICENSE"}` pointing at that AGPL
text, and it depends on `PyMuPDF`, which is itself AGPL/commercial dual-licensed
(`docs/UPSTREAM_REFERENCES.md:70`). The consequence for LabCairn was recorded
before any code was written: a statement of the form "*PaperQA2 is Apache-2.0*" is
**incomplete** (`docs/UPSTREAM_REFERENCES.md:74`), AGPL-3.0 is the strongest
copyleft in common use, and `paper-qa-pymupdf` is **study-only** for LabCairn
unless a deliberate licence decision is recorded
(`docs/UPSTREAM_REFERENCES.md:75`). The boundary is a *component* boundary, not a
repository boundary (`docs/UPSTREAM_REFERENCES.md:76`).

**`paperspine` is not a library and ships installers.** It contains no
`pyproject.toml`, no `setup.py` and no `setup.cfg`; it is a collection of agent
skills packaged for distribution into other agents' directories
(`docs/UPSTREAM_REFERENCES.md:81`). It nonetheless carries substantial source —
**439 `.py` files and 570 `.md` files** (`docs/UPSTREAM_REFERENCES.md:83`) — so
"*not a library*" must not be read as "*not code*". Its top level holds an
installer pair, an agent instruction file and a human installation guide next to
the study material, and all four are untrusted data that must not be run, followed
or copied (`docs/UPSTREAM_REFERENCES.md:85`). §6 returns to this.

### 1.4 The method that produced every observation in this dossier

The study followed the five-step workflow recorded at
`docs/UPSTREAM_REFERENCES.md:114`–`:127`: state the problem in LabCairn's terms;
select the relevant upstream components and inspect exact files and tests at the
recorded SHA; write an ADR naming the upstream URL, SHA and inspected paths, the
mechanism adopted or rejected, LabCairn's own interface and test plan, and a
licence note if source is copied; implement under LabCairn's own design
constraints with unit and integration tests; and benchmark the *behaviour* on a
small relevant fixture, never claiming superiority from source inspection alone.

**One rule from that workflow changed how upstream is read, and it is worth a
reviewer's attention.** During the `deepagents` study, the project's own
documentation advertised a planning capability in four places, and the code at the
pinned commit did not have it — the middleware stack assembled by
`create_deep_agent` contains no planning or todo middleware, the public signature
has no planning parameter, and the tool comes from another project's middleware
reached only through an opt-in profile. The removal is on the record as a
breaking change; the prose was never updated
(`docs/UPSTREAM_REFERENCES.md:52`). The rule adopted from that is stated in the
same place:

> **A README, docstring or architecture overview is a claim, not evidence — a
> capability counts only when a code path constructs it.**
> (`docs/UPSTREAM_REFERENCES.md:52`)

LabCairn applies this rule to itself as well: the ADRs separate what was
**observed in code** from what was **inferred**, and mark the inferences.

---

## 2. LabCairn's independent implementation, design by design

Each row states the upstream design that was studied, the LabCairn contract that
resulted, and the test that witnesses it. **The upstream column is a reference to
a recorded observation**; the upstream source is not in this repository and none
of it is reproduced here.

### 2.1 Model and tool execution boundary — ADR-0002

**Studied:** `pydantic-ai` and `openhands-sdk`, at the SHAs in §1.1.
Recorded in `docs/adr/ADR-0002-model-and-tool-execution-boundary.md`.

| Upstream design studied | LabCairn's own contract | Where it lives | Witness |
|---|---|---|---|
| A tri-state cost field alongside integer token counters that default to zero | `UsageValue = Known \| Unknown`; `Unknown` carries a reason and has no numeric value, so summing over it raises rather than producing a number | `src/labcairn/core/providers/usage.py:197` (the union), `:114` (`Known`), `:159` (`Unknown`) | `tests/test_provider_budget.py::test_a_measured_zero_passes_every_ceiling`, `::test_a_half_measured_response_leaves_the_total_unknown`, `::test_budget_module_contains_no_numeric_coercion` |
| Capability flags resolved from the model *name* rather than probed | `ProviderCapabilities` + `ProviderProbe`: real requests against the configured endpoint, an unprobed capability treated as unsupported, probe results cached per (endpoint, model, protocol) | `src/labcairn/providers/capabilities.py`, `src/labcairn/providers/probe.py` | `tests/test_provider_capabilities.py::test_model_profile_name_match_is_not_capability_evidence`, `::test_probe_never_reads_a_model_profile`, `::test_probe_unsupported_tool_calling_fails_closed_without_text_parsing`, `::test_capability_unverified_behaves_as_unsupported` |
| A budget ceiling that warns and proceeds when the cost cannot be priced | Ceilings fail **closed**: an unpriced cost with a cost ceiling halts the run; an unproven usage-reporting capability blocks a token ceiling **before** the request | `src/labcairn/providers/budget.py` | `tests/test_provider_budget.py::test_cost_ceiling_fails_closed_when_price_unknown`, `::test_token_ceiling_fails_closed_when_tokens_unknown`, `tests/test_provider_adapter.py::test_capability_failure_decided_before_request_not_after` |
| A request counter that excludes provider-side retries | `max_model_requests` bounds LabCairn-issued requests; provider attempts are recorded separately so a report can show the gap | `src/labcairn/providers/ledger.py`, `budget.py` | `tests/test_provider_budget.py::test_provider_retry_does_not_consume_model_request_budget`, `::test_the_ledger_reports_both_counters_so_a_report_can_show_the_gap` |
| A tool-call counter that counts successes | `max_tool_calls` counts **attempts**, so a failing-tool loop is bounded | `src/labcairn/providers/budget.py` | `tests/test_provider_budget.py::test_tool_calls_are_counted_as_attempts_not_successes` |
| A closed failure vocabulary with the third-party detail discarded | `FailureKind` + `OperationFailure`: the raw detail is redacted and only a digest is persisted | `src/labcairn/providers/errors.py:60`, `redaction.py` | `tests/test_provider_redaction.py::test_a_classified_failure_carries_no_field_that_can_hold_third_party_text`, `::test_classification_uses_the_status_code_and_discards_the_body` |

**Why this is an independent implementation and not a port.** The upstream
vocabulary does not survive into LabCairn: upstream's confirmation policy returns
a boolean and cannot express a denial, upstream's approval is a wire-level label
on the tool rather than an enforcement point, and upstream has no probe at all.
The LabCairn contracts define their own verdict vocabulary, their own failure
classes and their own policy layer, and each divergence is recorded in ADR-0002
with the upstream observation that forced it.

### 2.2 Event and permission model — ADR-0003

**Studied:** `openhands-sdk` and `deepagents`, at the SHAs in §1.1.
Recorded in `docs/adr/ADR-0003-event-and-permission-model.md`.

| Upstream design studied | LabCairn's own contract | Where it lives | Witness |
|---|---|---|---|
| Immutable, frozen, closed event records | An application-owned event log in SQLite: per-Task gapless `seq` allocated inside the transaction, a closed event vocabulary, event and state rows committed together | `src/labcairn/runtime/event.py`, `src/labcairn/db/repository.py`, `src/labcairn/db/models.py` | `tests/test_store_events.py::test_interleaved_tasks_each_get_a_gapless_run_from_one`, `::test_seq_is_not_the_primary_key`, `::test_after_seq_returns_the_contiguous_tail`; `tests/test_store_atomicity.py::test_a_failure_between_events_and_state_rolls_back_both` |
| A confirmation policy that returns a boolean | `allow / ask / deny`, evaluated **deny first**, defaulting to deny, with no ordering escape | `src/labcairn/security/policy.py` | `tests/test_security_policy.py::test_deny_beats_allow_and_ask`, `::test_default_is_deny`, `::test_rule_declaration_order_does_not_change_the_verdict` |
| A filesystem-path permission layer whose default is allow and whose first match wins | The same **techniques** (symlink-resolved double-checking, filtered read results, construction-time pattern validation) under an opposite default; deny-wins generalised from one operation to all | `src/labcairn/security/policy.py`, `src/labcairn/security/paths.py` | `tests/test_security_policy.py::test_denied_entries_are_filtered_out_of_a_listing`, `::test_a_deny_on_the_resolved_spelling_blocks`, `::test_a_deny_on_an_ancestor_blocks` |
| An approval that is a transient UI flag | A durable approval row bound to a canonical-arguments digest, a task scope, an expiry and a single-use rule | `src/labcairn/security/approval.py`, `src/labcairn/application/approvals.py` | `tests/test_security_approval.py::test_approval_rejected_when_arguments_change`, `::test_expired_approval_is_not_reusable`, `::test_approval_is_single_use`, `::test_approval_invalidated_by_source_change` |
| Crash recovery that synthesises an error event for an unmatched action | An explicit `UNCERTAIN` operation state that recovery **enters**, plus a read-only reconciliation probe; no replay without a resolution | `src/labcairn/recovery/reconciliation.py`, `executor.py`, `resume.py` | `tests/test_recovery_crash_matrix.py::test_at2_crash_after_write_before_commit_marks_uncertain_and_blocks_replay`, `::test_at2b_the_write_counter_proves_no_second_write_during_reconciliation`, `::test_at6_reconciliation_flags_conflicting_content_for_human` |
| Prompt-level defences against injected instructions | A **structural** defence: the policy evaluator's input surface admits only application-supplied values, so no document text can reach a decision | `src/labcairn/security/untrusted.py`, `policy.py` | `tests/test_security_injection.py::test_an_injected_document_cannot_create_a_rule`, `::test_policy_input_surface_is_closed`, `::test_there_is_no_parser_that_turns_text_into_a_rule` |

**The one that is most clearly a divergence rather than a borrowing.** ADR-0003
records the upstream philosophy as *"trust the LLM ... enforce boundaries at the
tool/sandbox level"* and adopts the opposite: deny-wins, default-deny, inside the
application, before any sandbox exists. The techniques survive the disagreement
because a technique is independent of the default it runs under. **That is the
whole point of the two words "referenced" and "reused" being different.**

### 2.3 Scientific provenance and evidence model — ADR-0004

**Studied:** `paper-qa` and `paperspine`, at the SHAs in §1.1.
Recorded in `docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md`.

| Upstream design studied | LabCairn's own contract | Where it lives | Witness |
|---|---|---|---|
| Citation keys that are hashes of a *summary*, checked by string containment in the answer | Four independent checks — C1 source existence, C2 quotation match, C3 numerical consistency, C4 scientific interpretation — that cannot be inferred from one another | `src/labcairn/evidence/checks/c1.py`, `c2.py`, `c3.py`, `src/labcairn/evidence/cite_support/__init__.py` | `tests/test_cite_c1.py::test_page_99_of_a_3_page_document_fails`, `::test_an_anchor_id_that_does_not_exist_fails`; `tests/test_cite_c2.py::test_no_rung_of_the_ladder_lets_a_paraphrase_through`, `::test_an_indeterminate_c2_never_promotes_a_record`; `tests/test_cite_c3.py::test_absent_tolerance_is_not_zero_tolerance`, `::test_c3_does_not_convert_units` |
| A deterministic abstention when the retrieved context is empty | Requirement A6: an explicit *no evidence found* result; the flow does not call the model with empty evidence and does not produce an answer | `src/labcairn/evidence/retrieval.py` | `tests/test_evidence_retrieval.py::test_a_query_that_misses_reports_no_hit_and_not_a_failure`, `::test_a_search_that_breaks_reports_a_provider_failure_not_a_no_hit` |
| A ledger whose validation checks graph integrity only and never reads a source file | A ledger in application-owned SQLite whose records carry anchors, content hashes and an append-only verification log | `src/labcairn/evidence/record.py`, `store.py`, `gate.py` | `tests/test_evidence_gate.py::test_a_fabricated_source_fails_the_gate`, `::test_a_record_with_no_anchor_at_all_fails`; `tests/test_evidence_contracts.py::test_verification_states_are_exactly_the_six_architecture_declares` |
| Scientific interpretation demoted to a warning while link existence is promoted to a failure | That asymmetry promoted from a convention into a typed contract: the C4 check **exists**, has a signature, and always returns `not_checked` — never absent, never green | `src/labcairn/evidence/cite_support/__init__.py` | `tests/test_evidence_contracts.py::test_c4_always_returns_not_checked`, `::test_no_state_means_scientifically_established`, `::test_c4_cannot_enter_the_verification_log_as_a_pass` |
| A locator expressed as a human-readable display string | Typed, structured locators: page-and-character-range for PDF, line-and-section for text, row-and-column for CSV, sheet-and-cell for XLSX | `src/labcairn/sources/locators.py`, `src/labcairn/sources/primitives.py` | `tests/test_source_contracts.py::test_locator_kinds_are_closed_at_five_members`, `::test_every_locator_kind_locates_and_round_trips`, `::test_csv_locator_requires_row_and_column` |
| "Found nothing" and "could not look" kept apart | The same split, reimplemented, as distinct retrieval outcomes that cannot be confused | `src/labcairn/evidence/retrieval.py` | `tests/test_evidence_retrieval.py::test_the_two_negatives_cannot_be_the_same_value` |

**The licence constraint applied here is a real constraint, not a formality.**
ADR-0004 records that no design conclusion in it is sourced from the AGPL
subpackage: every `paper-qa` finding cites only the Apache-2.0 core, and the AGPL
subpackage was opened only to read its licence header. The `paperspine` locator
idea is MIT and was reimplemented.

### 2.4 The decisions that were LabCairn's own, with no upstream borrow

Recorded here because "referenced" and "owned" are both true for these, and a
reviewer scanning the ADR directory should be able to tell them apart without
opening each file.

| ADR | Decision | Upstream borrow? |
|---|---|---|
| ADR-0005 | Application owns research semantics; the framework owns model interaction | Builds on ADR-0002's observations; the *split* is LabCairn's |
| ADR-0006 | Capability namespaces stay disjoint; outbound is a permission capability | **None.** ADR-0006 states this explicitly: *"This is an internal design decision, not an upstream borrow"* |
| ADR-0007 | Event payload shape | None |
| ADR-0009 | Material and extracted-text storage | None |
| ADR-0010 | Readability and disclosures | None |
| ADR-0011 | Canonical policy matching | None |
| ADR-0012 | Chart rendering library | A library *choice*, not an upstream borrow; it borrows the paper-qa **lesson** about bundled fonts hiding behind a permissive root licence |
| ADR-0013 | Report export libraries | As ADR-0012 |

### 2.5 Upstream designs that were studied and produced no LabCairn code

Some of the most careful study produced a refusal. These are listed so a reviewer
can see that the study was not one-sided.

| Studied | Outcome | Recorded in |
|---|---|---|
| `deepagents`' planning / todo middleware | **No planning middleware in the default stack at the pinned commit.** The catalogue entry was corrected rather than the ADR rewritten to match the prose | `docs/UPSTREAM_REFERENCES.md:52`, ADR-0003 §A6 |
| `deepagents`' subagent delegation and its ephemeral state backend | Rejected as a Stage mechanism: durability is delegated to an external checkpointer, and business state is co-mingled with conversation history | ADR-0003 §A6 |
| `openhands-sdk`'s per-event file `EventLog` and its lease / fencing-token scheme | The ideas adopted, the mechanism refused: ordering derived from a directory scan cannot prove contiguity, and thread-safety is not crash-atomicity | ADR-0003 §A1, §A4 |
| `openhands-sdk`'s non-native function calling | Refused, and flagged as unsafe: parsing the model's prose back into tool calls makes document text an injection vector into a side effect | ADR-0002 §A4 |
| `openhands-sdk`'s LLM-based injection analyzer as a primary defence | Refused as primary: a probabilistic signal cannot decide whether a write happens | ADR-0002 §A5 |
| `paper-qa` as a retrieval layer | Rejected on five independent grounds, one of which is the licence | ADR-0004 §A1 |
| `paperspine`'s ledger schema as a dependency | Rejected as a dependency; adopted as vocabulary and test cases only, reimplemented | ADR-0004 §A2 |

---

## 3. What was refused, and why

### 3.1 Upstream designs refused

| Refused | From | The reason, in one line | Recorded in |
|---|---|---|---|
| Static model-name capability lookup | `pydantic-ai` | A name lookup is not a capability fact; LabCairn probes | ADR-0002 §A1 |
| `int = 0` token usage | `pydantic-ai` | Zero and unknown are different facts | ADR-0002 §A1 |
| A cost limit that warns and proceeds | `pydantic-ai` | An explicit ceiling that silently does nothing is the failure the work order names | ADR-0002 §A1 |
| A request counter that excludes provider-side retries | `pydantic-ai` | It does not bound spend | ADR-0002 obs. 4 |
| Approval as a wire-level label | `pydantic-ai` | A label is not an enforcement point | ADR-0002 obs. 8 |
| Validation failure and model retry sharing one bucket | `pydantic-ai` | A policy denial must be terminal, not retryable | ADR-0002 obs. 7 |
| A confirmation policy that returns a boolean | `openhands-sdk` | It cannot express *deny* | ADR-0002 §A2 |
| Cost normalised to `0.0` | `openhands-sdk` | An unknown cost reads as zero and the budget never trips | ADR-0002 obs. 12 |
| Non-native tool calling by text parsing | `openhands-sdk` | It raises the injection surface exactly where LabCairn is exposed | ADR-0002 §A4 |
| An LLM risk analyser as the primary defence | `openhands-sdk` | A probability cannot gate a side effect | ADR-0002 §A5 |
| A file-per-event log with a directory-scan index | `openhands-sdk` | A one-event hole silently discards the history; contiguity must be provable | ADR-0003 §A1 |
| Crash recovery that asserts an interrupted action did not complete | `openhands-sdk` | An assertion is not a finding; nothing consulted the filesystem | ADR-0003 §A2 |
| Default-allow, first-match-wins permission resolution | `deepagents` | LabCairn requires deny-wins with default-deny | ADR-0003 §A5 |
| A permission layer scoped to seven built-in filesystem tools | `deepagents` | It is a path policy engine, not a capability gate; caller-supplied tools get no enforcement | ADR-0003 §A5, second verification pass |
| A plan kept as conversation content | `deepagents` / LangChain | A plan is a task artifact, not a new authoritative store | ADR-0003 §A6 |
| A subagent that inherits or replaces the parent's permissions | `deepagents` | A subtask that silently loses the parent's deny rules is a privilege-escalation path | ADR-0003 §A6 |
| A one-boolean-per-claim evidence model | — (simplest option) | It cannot express "the locator resolved but the quote did not match" | ADR-0004 §A3 |
| JSONL plus a periodic snapshot as the store | — (simplest option) | Two writes with no shared commit point cannot couple events to state | ADR-0003 §A7 |

### 3.2 Licences refused, and the one that was a near miss

- **PyMuPDF — refused, and it is the one that was nearly taken by default.**
  LC-P1-08's work order named PyMuPDF; ADR-0008 refused it and chose `pdfplumber`
  (MIT) instead. PyMuPDF is dual-licensed AGPL-3.0 / commercial, both branches
  cost something the project could not pay, and the AGPL argument rests on
  §§4–6 rather than §13 (the earlier draft cited §13 wrongly, and says so). The
  decision was made **on the assumption of a permissive root licence**, and that
  assumption is still open — see `docs/acceptance/LC-P1-14-font-licence-audit.md`
  and `docs/plans/LC-P1-13-14-task-breakdown.md` §1.4.1. **A reviewer should know
  that the licence decision this dossier leans on is not yet made.**
- **The `paper-qa-pymupdf` AGPL subpackage — refused.** Study-only, and no design
  conclusion in ADR-0004 is sourced from it (`docs/UPSTREAM_REFERENCES.md:75`).
- **The AI-Scientist v2 custom licence — refused by default**, on the grounds
  recorded at `docs/UPSTREAM_REFERENCES.md:48` and `:87`.
- **Copyleft hidden behind a permissive root line — refused twice more**, in
  ADR-0012 and ADR-0013, for report and chart libraries that bundle fonts or
  copyleft components under their own terms. That is the paper-qa failure mode
  applied to LabCairn's own dependencies.

### 3.3 The refusals that changed the design, not just the plan

Three refusals are worth a reviewer's attention because the upstream design was
*good* and the refusal was not about quality:

1. **Upstream's crash recovery.** It handles the write/HEAD half of the problem
   correctly and then resolves the ambiguity by asserting the action did not
   complete. LabCairn's `UNCERTAIN` state and its reconciliation probe exist
   because that assertion is exactly what the Phase 1 crash matrix forbids.
2. **Upstream's permission model.** It is a competent path-policy engine with a
   deny-wins rule for one dangerous operation, arrived at independently. LabCairn
   keeps the techniques and inverts the default, and the divergence is recorded as
   deliberate in ADR-0003.
3. **`paper-qa`'s retrieval layer.** It is the most attractive option on paper and
   was rejected on five grounds. The licence ground is the one a reader most
   needs, because it is the ground on which "just use the library" would have
   failed quietly.

---

## 4. The reuse boundary

### 4.1 The four tiers, stated

| Tier | What it is | Present in LabCairn? |
|---|---|---|
| **0 — Studied** | An upstream design was read at a pinned commit and an observation recorded | Five repositories, §1.1 |
| **1 — Referenced** | An upstream *idea* informed a LabCairn contract that was written here, with its own vocabulary and its own tests | §2 — this is the large majority |
| **2 — Declared library dependency** | Upstream *published as a package* and installed from a package index; its code is not in this repository | **One: `pydantic-ai`** — §4.3 |
| **3 — Copied or adapted upstream source** | Upstream file content present in this repository, in whole or in part | **None** — §4.2 |

### 4.2 Tier 3, measured

`docs/UPSTREAM_REFERENCES.md:186` records the LC-P1-00 acceptance bullet as
"vacuously satisfied: **no upstream source was copied or adapted**", on the
grounds that the tracked tree was then 14 LabCairn-authored files. That is a
record of a review that happened; it is **not** a live status, and it was not
carried forward. **It was re-measured on 2026-10-25 for this dossier.** Four
independent checks, and what each one found:

| # | Check | Result |
|---|---|---|
| 1 | `git ls-files` for any path matching the three reference families `_references*`, `.upstreams*`, `labcairn-upstreams*` (`docs/UPSTREAM_REFERENCES.md:156`) | **No upstream file is tracked.** The project's own matcher is segment-based rather than substring-based, and it deliberately lets `docs/UPSTREAM_REFERENCES.md` through as a **near miss that must stay visible** — `tests/test_no_reference_leakage.py:508` asserts that this file is *not* a reference path. That is the only near miss in the tracked tree, and it is LabCairn's own document about upstream. |
| 2 | `git log --all --diff-filter=A` for any upstream path ever added | **No upstream source tree has ever been tracked**, on any branch in this repository. The only added file a loose substring search finds is `docs/UPSTREAM_REFERENCES.md` — LabCairn's own document. |
| 3 | Grep of `src/` for upstream identifiers (`CANNOT_ANSWER_PHRASE`, `GROUP_PREFIXES`, `PRECISE_LOCATOR_RE`, `_check_fs_permission`, `should_confirm`, `ConfirmationPolicyBase`, `sanitize_messages`, `UsageLimits`, `TodoListMiddleware`, `EventLog`, …) | **Zero hits.** The identifiers that do appear — `ModelProfile`, `accumulated_cost`, `SecurityRisk`, `ErrorClassification` — appear only inside docstrings and comments, as citations to the observation that motivated a decision. |
| 4 | Grep of `src/` for the upstream *package* names (`pydantic_ai`, `openhands`, `deepagents`, `paperspine`, `paperqa`, `pqac-`) | Hits are **comments and docstrings only**, except the three import sites in §4.3. The same four names appear in `pyproject.toml` only inside comments that cite the paper-qa licence lesson — not as a dependency. |

**The names that coincide, and what that does and does not mean.** A reviewer
scanning for copied code will hit at least one name that matches an upstream
identifier, and the dossier should say so rather than let the reader find it and
wonder. `FailureKind` is an upstream enum name, and LabCairn has one at
`src/labcairn/providers/errors.py:60` — with its own twelve members, a
different set from the upstream one. What ADR-0002 §5 records is that the
upstream *shape* was studied — a closed four-field record whose raw third-party
detail is discarded rather than persisted — and reimplemented with LabCairn's
own vocabulary. **A shape is a design; a member list and a record type are
code, and those were written here.** The other coincident names —
`ModelProfile`, `accumulated_cost`, `SecurityRisk`, `ErrorClassification` —
occur in `src/` only inside comments that cite the observation that produced a
decision. A name is not an implementation, and this dossier says which of the
two it is in every case.

**The upstream trees are also not a build input.** The exclusion checklist
requires that the reference clones live outside the repository and that
`git ls-files`, the built sdist and the built wheel contain no reference path
(`docs/UPSTREAM_REFERENCES.md:163`, `:164`), and it records that the sibling
directory is itself unprotected because `.gitignore` does not reach above its own
directory (`docs/UPSTREAM_REFERENCES.md:173`). `tests/test_no_reference_leakage.py`
is what turns that from a promise into a gate — 26 test functions, measured
2026-10-25, covering the tracked-file listing, the built artifacts, the git
ignore rules under every case variant, the workflows, and
`test_no_module_level_dependency_on_the_sibling_reference_directory`.

**And the one acceptance bullet that was never discharged is now discharged by
the other half.** `docs/UPSTREAM_REFERENCES.md:185` records "no hard runtime/CI
dependency on reference clones" as only partially testable at LC-P1-00, because
there was no build system. There is now: a Hatchling build with an explicit
recursive package root, and the `reference-exclusion` required status check
(`docs/UPSTREAM_REFERENCES.md:191`, `:192`). An external contributor can build
LabCairn without any of the five clones present.

### 4.3 Tier 2, stated plainly: `pydantic-ai` is an installed dependency

This is the one place where "no upstream code was reused" would be misleading if
read carelessly, so it is written down rather than left for a reader to discover.

- `pydantic-ai>=1,<2` is a **declared runtime dependency** in `pyproject.toml`,
  resolved in `uv.lock`, and installed from the package index.
- It is **imported in three modules**, all of them inside the provider layer:
  `src/labcairn/providers/pydantic_models.py:137`–`:138` and `:149`–`:150`, which
  construct the upstream model object for the Anthropic and OpenAI-compatible
  protocols; `src/labcairn/providers/probe.py:473`–`:476`, which builds the
  request objects the capability probes send; and
  `src/labcairn/providers/adapter.py:520`–`:523`, where the adapter builds the
  upstream request and calls the upstream model before **translating** the
  upstream response into LabCairn's own `ModelResponse`.
- **No upstream file is in this repository.** The dependency is used as a library
  behind a protocol (`ModelProvider` in `src/labcairn/core/providers/protocol.py`)
  that a hand-rolled adapter could replace without touching persisted schemas —
  which is the reversibility argument ADR-0002 makes explicitly.
- ADR-0005 records the ownership split this implements: the framework owns how a model is *called*; the application owns what is *known*.
- **No upstream *type* appears in a persisted schema.** The upstream message list is a derived, non-authoritative projection rebuilt from LabCairn's own event log.

`tests/test_provider_adapter.py::test_the_adapter_satisfies_the_frozen_provider_protocol`
witnesses the seam, and `tests/test_fake_provider_isolation.py` witnesses that the
rest of the system runs with no upstream library in the picture at all.

**The other four repositories are not dependencies and are not imported
anywhere.** `paper-qa`, `paperspine`, `openhands-sdk` and `deepagents` appear in
`pyproject.toml` only inside comments that cite the paper-qa licence lesson,
never in the dependency list; they are absent from `uv.lock`; and no module in
`src/` or `tests/` imports any of them.

### 4.4 Third-party material that *does* reach a user

For completeness, because a reader comparing "what is third-party in the shipped
artefacts" will ask: the third-party material that ships comes from **declared
package dependencies**, not from the five studied repositories. The
[font audit](acceptance/LC-P1-14-font-licence-audit.md) measured it: no
third-party font file reaches any artefact — the PDF references the Type 1 core
faces and embeds nothing, the DOCX names fonts in a table and carries none, and
the figure is a raster. The GPL-licensed font that `reportlab`'s wheel bundles
does not attach to anything a user receives.

### 4.5 What would have to change if this document is wrong

The tier-3 claim is falsifiable in a way a reviewer can check directly, and it
should be: if any upstream source were present in the tree, the checks in §4.2
would find it, `tests/test_no_reference_leakage.py` would fail, and §4.3's
three-import-sites statement would be false. **The claim is stated so that it can
be made false.** A reviewer who believes otherwise can read
`src/labcairn/providers/` and `pyproject.toml` and check.

---

## 5. LabCairn's own tests — where the independent implementation is witnessed

### 5.1 The suites that witness each upstream-referenced design

| Upstream-referenced design | LabCairn's witnesses |
|---|---|
| Tri-state usage and pre-flight budgets | `tests/test_provider_budget.py`, `tests/test_provider_adapter.py`, `tests/test_fake_provider_usage.py` |
| Probed capability detection | `tests/test_provider_capabilities.py`, `tests/test_fake_provider_isolation.py` |
| Failure classification and redaction | `tests/test_provider_redaction.py`, `tests/test_provider_adapter.py` |
| Application-owned event log | `tests/test_store_events.py`, `tests/test_store_atomicity.py`, `tests/test_store_concurrency.py`, `tests/test_store_persistence.py` |
| Deny-wins permission evaluation | `tests/test_security_policy.py`, `tests/test_security_listing_canonical.py` |
| Digest-bound approvals | `tests/test_security_approval.py`, `tests/test_recovery_approvals.py` |
| Structural anti-injection | `tests/test_security_injection.py`, `tests/test_refusal_witnesses.py` |
| `UNCERTAIN` and reconciliation | `tests/test_recovery_crash_matrix.py`, `tests/test_recovery_resume.py` |
| Four independent cite-support checks | `tests/test_cite_c1.py`, `tests/test_cite_c2.py`, `tests/test_cite_c3.py`, `tests/test_evidence_contracts.py` |
| Retrieval outcomes that keep "no hit" and "failed" apart | `tests/test_evidence_retrieval.py`, `tests/test_retrieval_ground_truth.py` |
| The evidence gate and the fabricated-source case | `tests/test_evidence_gate.py`, `tests/test_evidence_store.py` |
| Structured locators and material ingestion | `tests/test_source_contracts.py`, `tests/test_material_adapters.py`, `tests/test_material_pdf.py` |
| The upstream exclusion itself | `tests/test_no_reference_leakage.py` |

### 5.2 How to run them

The suite is run with a base temp directory **outside** the repository and a
per-process `TEMP`/`TMP`/`MPLCONFIGDIR`; two runs must not share one base temp
directory, and the status of a command is read from the command rather than from
a pipeline. The rules are in `CLAUDE.md`, and the reasons are measured rather
than stylistic.

### 5.3 The size of the independent test suite, and how it was counted

**2292 `def test_` definitions across 106 test modules**, measured on 2026-10-25 on
the tree named at the top of this document by counting `def test_` occurrences
under `tests/`. **This is a definition count, not a case count**: parameterised
cases expand it, and a collected run reports more. The LC-P1-01 record counted
99 tests in `tests/test_no_reference_leakage.py` alone
(`docs/UPSTREAM_REFERENCES.md:192`); that file now defines 26 test functions,
six of them parameterised, so the two figures are not measuring the same thing
and **neither is carried forward as a fact about the suite.**

The point of the number is not the number. It is that **the upstream behaviour
LabCairn refused has a witness too**: `tests/test_provider_capabilities.py::test_model_profile_name_match_is_not_capability_evidence`
exists to fail if LabCairn ever starts believing a model name, and
`tests/test_security_policy.py::test_deny_beats_allow_and_ask` exists to fail if
LabCairn ever starts resolving rules first-match-wins. **A refusal that nothing
watches is a preference, and this repository does not ship preferences.**

---

## 6. The security boundary this dossier does not cross

**The upstream trees contain a measured prompt-injection corpus, and none of it
is here.** The five clones contain **139 files named `AGENTS.md`, `CLAUDE.md` or
`SKILL.md`** (`docs/UPSTREAM_REFERENCES.md:142`): `pydantic-ai` 59, `deepagents`
43, `openhands-sdk` 29, `paperspine` 8, `paper-qa` 0. `SKILL.md` is an entire
file format whose purpose is to instruct an agent, and three of the five
repositories ship 22–26 of them. `paperspine` is the sharpest instance: its top
level holds an agent instruction file and an installation guide next to an
installer pair, so the four highest-risk artefacts are the four most
conveniently reachable files in the tree (`docs/UPSTREAM_REFERENCES.md:143`).

The rules that follow from that measurement, and that this dossier obeys:

- External source files, agent prompts, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`,
  issue text, CI scripts and examples are **untrusted input**, not LabCairn
  development instructions (`docs/UPSTREAM_REFERENCES.md:141`).
- **Cloning does not imply executing.** No install script, setup script, test
  command or entrypoint from any upstream tree was run (`docs/UPSTREAM_REFERENCES.md:144`).
- **Third-party source trees and full extracted source snippets are not
  committed** into any directory that might be bundled or published
  (`docs/UPSTREAM_REFERENCES.md:146`).
- Upstream code is not ingested wholesale into a model's context; only relevant
  files and ranges are opened (`docs/UPSTREAM_REFERENCES.md:147`).

**This is why the dossier quotes no upstream file content.** Everything above
about upstream is either (a) a pointer to a line in
`docs/UPSTREAM_REFERENCES.md`, which is a LabCairn document about upstream, or
(b) a pointer to an ADR section, which records a *conclusion* about an upstream
path. **Reproducing upstream text here would put untrusted bytes into a
LabCairn document**, and this document is the one a reviewer is most likely to
read with an assistant beside them. The observation is enough; the quotation is
not needed, and the quotation is the risk.

---

## 7. What this dossier does not establish

Stated plainly, because a dossier that lists only its strengths is a brochure.

1. **No superiority claim, and no comparison.** `docs/EVALUATION.md:29` permits a
   comparison only on like-for-like matched tasks with verified capabilities and
   stated limitations. No such baseline was run for this dossier, so no ranking
   over PaperQA2, PaperSpine or any other project appears anywhere above.
   Making one would require: matched tasks over the same fixtures, a second
   installation of each baseline, and stated confidence intervals — the scope the
   owner has been asked to settle in `docs/plans/LC-P1-13-14-task-breakdown.md`
   §1.4.3.
2. **The upstream observations are second-hand here.** This document reports what
   was observed at the pinned commits on 2026-10-15, as recorded in the ADRs. It
   does not re-verify those observations against the upstream trees, and it cannot
   — the trees are not in this repository, and `docs/UPSTREAM_REFERENCES.md:34`
   already records that neither the local snapshot nor upstream's retention of the
   commits is permanent. **A reader who wants to check an upstream claim goes to
   the upstream path named in the ADR, at the SHA named in §1.1.**
3. **The licences are recorded, not adjudicated.** `docs/UPSTREAM_REFERENCES.md:30`
   says the labels "are still not a legal assessment, and transitive dependencies
   may carry other licences." §1.3 repeats that. Nothing here is legal advice.
4. **The root licence of LabCairn is not settled.** `LICENSE.PENDING.md` grants
   nothing, and the PyMuPDF refusal in §3.2 was made on the assumption of a
   permissive root licence that has not been decided. A reader who cares about
   whether LabCairn *may* be released permissively must read
   `docs/acceptance/LC-P1-14-font-licence-audit.md` and
   `docs/plans/LC-P1-13-14-task-breakdown.md` §1.4.1.
5. **The claims here are about a tree, not about the product.** Everything is
   stated at `dd08573`. A later change can make this document wrong, and the
   project rule applies to it as to everything else: *a value that can change is
   re-measured, not carried forward.*
6. **The dossier has no witness of its own yet.** §4.2's checks were run by hand
   for this document; they are not yet a test that fails when they stop being
   true. That is a real gap, and it is the one thing in this document that the
   project would want closed before the alpha ships.

---

## 8. The record this document discharges

`docs/UPSTREAM_REFERENCES.md:187` carries the LC-P1-00 acceptance bullet:

> *P1 review dossier names relevant upstream designs and clearly identifies
> LabCairn's independent implementation and its tests.* — **Belongs to LC-P1-14
> (G5).** Not achievable now: there is no implementation and no LabCairn test
> suite to distinguish from upstream behaviour.

**The reason it was not achievable then no longer holds.** LabCairn has an
implementation and its own test suite, and §2 names the design, the contract and
the witness for each; §3 names what was refused; §4 measures the boundary and
states the one dependency; §5 is the index a reviewer uses to ask "is this
property tested?".

**What this document does not do is check the checkbox.** The checkbox is
`docs/UPSTREAM_REFERENCES.md`, a file this task does not own and did not edit.
Whether the bullet is now checked is a decision for the gate, not for this
document.
