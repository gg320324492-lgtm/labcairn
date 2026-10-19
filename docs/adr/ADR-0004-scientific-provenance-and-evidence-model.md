# ADR-0004: Scientific provenance and evidence model

**Status:** Proposed
**Work order:** LC-P1-09 (evidence ledger and cite-support validator); prerequisite input for LC-P1-08 (source locators) and gate G3 (evidence path)
**Date:** 2026-10-15

> **Execution note, 2026-10-18 (LC-P1-09 T05a).** One seam this ADR assumed
> and never specified: `SourceIndex`'s members. Contract 3 names the type in
> three signatures and never says what it is — that Protocol exists only in
> `src/labcairn/evidence/cite_support/__init__.py`. As written it had two
> members, `locate(anchor: SourceAnchor)` and `content_hash(source_id: str)`,
> and **neither accepts an anchor id** — which is all an `EvidenceRecord`
> carries (`anchor_ids: tuple[str, ...]`, ids deliberately, so a source cannot
> be mutated by editing the record that cites it).
>
> So this ADR's C1 requirement to *"fail if an anchor id is unknown"* had no
> implementation behind it and could not have had one. Revision 0007 adds the
> missing registry (`source_anchors`) and a third member,
> `load_anchor(anchor_id) -> SourceAnchor | None`. This **executes the
> requirement rather than amending it**; no signature, verdict vocabulary or
> transition condition here changes.
>
> Two decisions in that seam are worth this ADR's attention because they are
> not obvious and are easy to undo by accident:
>
> * **`load_anchor` returns `None` only for "no such id."** A row that exists
>   but whose address cannot be rebuilt raises `LocatorKeyError` instead. Both
>   make C1 answer `fail`, but "the ledger has never heard of this source" and
>   "the ledger has a broken row" are different findings and different repairs,
>   so collapsing them is the A12 confusion arriving by a new route.
> * **The registry stores one locator representation**, the canonical
>   `locator_key`, not the eight typed columns `source_texts` also carries.
>   With both, a reader would have to choose which to rebuild the anchor from,
>   and choosing wrong does not raise — it yields a *different valid* address
>   that C1 then resolves against the wrong page. That is this ADR's A1
>   ("never cite the nearest page") arriving by a route nobody was watching.
>
> Still true below, unchanged: C4 is never implemented in Phase 1. `IMPLEMENTED_CHECKS`
> is now every check, because C1, C2 and C3 landed in T05-T07 -- what still
> separates them is that C4 can never return a pass.

> **Execution note, 2026-10-19 (LC-P1-09 T06).** One vocabulary this ADR
> closed, and C2 turned out to need a fourth member of it.
>
> `NormalizationProfile` is fixed here as a closed set of three -- `exact`,
> `nfkc_whitespace_collapsed`, `nfkc_whitespace_collapsed_ligatures` -- with
> the note that "the *transforms* are LC-P1-09's; this contract fixes the
> vocabulary so the answer is comparable across runs and across records." The
> transforms, then, are this work order's to build, and the *shape* of the
> answer is what the vocabulary fixes.
>
> Measured against this repository's own papers, the three are not enough.
> Of the 21 (phrase, page) pairs in `tests/fixtures/retrieval/ground_truth.json`
> whose phrase a human confirmed on the page, **14 appear character-for-character
> in the stored text and 7 do not**. Page 3 of `arx-2610.09396` stores
> `StructuredDisambiguationforText-to-SQL`: ADR-0008 constraint 3 records that
> these PDFs space words by positioning, and the extractor *synthesises* the
> space from the gap between glyphs. Whether a word pair comes out with a space
> is a property of the extractor in that moment, not of the document.
>
> A quotation check that accepts only verbatim matches therefore calls a third
> of the corpus's genuine quotations unsupported -- which is R2's named failure
> ("a matcher whose aggressiveness is invisible generates false negatives, and
> false negatives teach users to turn the check off"), except that the
> aggressiveness would not even be visible, because the check would not have
> been lenient at all.
>
> Measured before deciding, so the cost is a number and not a worry:
>
>   - verbatim match:                      14/21
>   - match ignoring word boundaries:      21/21
>   - false positives on the four negative
>     queries (phrases absent from all
>     three papers, including "retrieval
>     augmented generation"):               0
>   - paraphrase probes:                    0
>
> So `word_boundaries_removed` joins the vocabulary, and revision 0008 rebuilds
> `verification_records` to widen the CHECK -- SQLite cannot ALTER one.
>
> **What this does not change.** A match reached only under the new profile is
> `indeterminate`, never `pass`; that is A4 and it is why the profile is a named
> member rather than a private step inside C2. An audit row recording
> `nfkc_whitespace_collapsed` for a comparison that deleted every space would be
> an audit row lying about how lenient the check was, which is R2's objection
> in a single field. No signature, verdict vocabulary or transition condition
> here changes; the vocabulary grows by one, and the reason is measured.

## Context and concrete problem

LabCairn's differentiating claim is that the evidence chain is traceable: literature, data, analysis, claims and results must each resolve to a located source with a declared verification state. `docs/ARCHITECTURE.md` fixes six verification states — `planned`, `extracted`, `verified_by_rule`, `user_attested`, `conflicted`, `unsupported` — and adds a constraint that is the hard part of this ADR:

> `verified_by_rule` can mean numeric/structural verification; it must not imply a scientific hypothesis is established.

`docs/PHASE_1_WORKORDERS.md` LC-P1-09 makes this concrete. The cite-support validator must distinguish **four different things**, which we name here:

- **C1 source existence** — does the cited source exist and does the locator resolve against the ingested material?
- **C2 quotation match** — does the quoted text actually appear, verbatim, at that locator?
- **C3 numerical consistency** — does the stated number agree with the number at the anchored cell/segment, under a declared tolerance and unit?
- **C4 scientific interpretation** — is the interpretation the author draws from the evidence scientifically warranted?

LC-P1-09 acceptance requires that fabricated DOIs/sources, wrong locators, missing evidence and conflicting numbers all fail the final evidence gate. `docs/ARCHITECTURE.md` additionally requires that retrieved excerpts are data and never instructions.

The concrete problem: **none of the four checks can be inferred from the others**, and a system that collapses them will report false confidence. In particular C4 is not a check that any Phase 1 system can honestly perform. A design that does not say so out loud will quietly let `verified_by_rule` drift into meaning "we checked the science," which is precisely the failure the architecture document forbids.

This ADR therefore fixes three things before any code: the `EvidenceRecord` contract, the state machine's transition conditions, and the four validator interfaces — including an explicit, testable statement of when the system must say "I don't know."

## Alternatives, including simpler/no-dependency option

### A1. Adopt PaperQA2 as the retrieval layer, adapt its session model as the ledger (REJECTED)

This was the most attractive option on paper: PaperQA2 already does chunking, embedding retrieval, per-chunk LLM summaries with relevance scores, and it emits answers with `(pqac-XXXXXXXX)` citation keys that it filters for hallucination. LC-P1-09 would collapse into a wrapper.

Rejected on five independent grounds, each sufficient:

1. **Its "cited" evidence is a summary, not the source text.** `src/paperqa/core.py::_map_fxn_summary` builds each `Context.context` by asking the summary LLM for a summary plus a self-assigned `relevance_score` 0–10 (`Context.score`). That string is not verbatim source text. C2 (quotation match) is therefore unimplementable against it: LabCairn could never verify a quote against the indexed representation, only against the summary of it. Rejected the same way for C3.
2. **Its support check is reference existence, not support.** `src/paperqa/types.py::PQASession.used_contexts` is `{c.id for c in self.contexts if c.id in self.raw_answer}` — a substring test for whether a context *ID token* appears in the answer. `PQASession.populate_formatted_answers_and_bib_from_raw_answer` then strips citation keys not present in `id_to_name_map`. That is C1, and only C1. Nothing in the codebase asks whether the answer sentence is actually entailed by the cited context.
3. **Locators are display strings, not addresses.** `src/paperqa/readers.py::_make_chunk` sets `Text.name` to `f"{doc.docname} pages {name}"` (e.g. `"Wiki2023 pages 1-3"`), line-based chunking to `f"{doc.docname} lines {last_line_i}-{line_i}"`, fixed chunking to `f"{doc.docname} chunk {i + 1}"`. Page ranges do survive inside the string, but there is no structured, re-derivable, schema-bound locator. LC-P1-08's "fixtures validate page, row, column and spreadsheet cell anchors **exactly**" cannot be built on a prose label.
4. **Dependency and architecture mismatch.** `pyproject.toml` pulls litellm, aviary, `lmi`, tiktoken, pybtex and an embedding stack. LabCairn's stack is Python 3.12 + Pydantic v2 + SQLite + SQLAlchemy/Alembic + FastAPI/Typer, with Pydantic AI reserved for model/tool interaction and explicitly *not* as authoritative storage. Making an LLM-summary-centric retriever the substrate would invert that separation.
5. **License.** See "License obligations" below: the PDF-parsing subpackage of the very project would be a dependency, and it is AGPL-3.0.

What we take from it is three *ideas*, each reimplemented independently: hash document **contents** rather than paths (`Doc.content_hash`); strip citation-shaped tokens that could collide with the system's own grounded IDs before handing text to an answer model (`core.py` line 358, `strip_citations`); and abstain deterministically when there is nothing to answer (see `docs.py` line 649, below).

### A2. Adopt PaperSpine's evidence ledger schema (REJECTED as a dependency, PARTIALLY ADOPTED as vocabulary)

PaperSpine is MIT and its ledger discipline is genuinely good — see "Upstream evidence". But it is a *manuscript-rewriting* pipeline whose ledger is a Markdown/JSON artifact set for a paper being written, not a durable task-scoped store with transactional events. Its `scientific_evidence_check.py::validate` checks graph integrity only. Taking it as a dependency would also import an agent-skill distribution package whose entire purpose is installing itself into Claude/Codex/Hermes/OpenClaw directories — a delivery model LabCairn explicitly does not share (`docs/ARCHITECTURE.md`: no MicroBubble runtime, no plugin installation sources).

Adopted as **vocabulary and test cases only**, reimplemented: the S/C/N/M/O/R record-group split, the rule that a record claiming a final state must also name *who or what* established it, the `absence_scan` evidence kind, and the separation of "search returned nothing" from "search failed."

### A3. Simplest possible option: one boolean `evidence_ok` per claim (REJECTED)

A boolean cannot express "the locator resolved but the quote did not match," which is the exact case LC-P1-09's acceptance list requires to fail. It also cannot express "we did not check," which is the honest state of C4 in Phase 1. Rejected: six states exist because the interesting cases are the intermediate ones.

### A4. Adopt both as-is and defer the model (REJECTED)

Rejected for the same reasons as A1/A2 combined, plus a LabCairn-specific one: `docs/ARCHITECTURE.md` requires "Conversation text is neither the task state nor scientific evidence by itself." An LLM-authored ledger is exactly conversation text. The ledger must be application-owned and deterministic.

## Upstream evidence (reference only)

Both SHAs were confirmed read-only immediately before writing this ADR; no clone, move, checkout or execution was performed.

```
git -C E:/labcairn-upstreams/paper-qa    rev-parse HEAD -> 57e89f7223b0960d5ee5ea048c69e3c47e088572  (verified 2026-10-15)
git -C E:/labcairn-upstreams/paperspine  rev-parse HEAD -> 42312b8d9c76ab25990cddfd76e3622276854118  (verified 2026-10-15)
```

### paper-qa

- **Repository URL:** https://github.com/Future-House/paper-qa
- **Exact commit SHA:** `57e89f7223b0960d5ee5ea048c69e3c47e088572` (verified)
- **Inspected paths:** `src/paperqa/types.py`, `src/paperqa/core.py`, `src/paperqa/docs.py`, `src/paperqa/readers.py`, `src/paperqa/prompts.py`, `src/paperqa/utils.py`, `src/paperqa/settings.py`, `src/paperqa/agents/tools.py`, `src/paperqa/agents/env.py`, `tests/test_paperqa.py`, `tests/test_agents.py`, `LICENSE`, `packages/*/LICENSE`.

**What was actually observed (not assumed):**

- `types.py::Doc.content_hash` is documented in-source as "the document's contents itself" and is populated by `DocDetails.populate_content_hash` → `utils.md5sum`. `DocDetails.__add__` discards `content_hash` to `None` when two variants of the same work carry different hashes, rather than picking one. **Observed.**
- `types.py::Context.populate_id` derives the citation key `pqac-{8-char hash}` from `question + context[:500]` (`Context.ID_HASH_LENGTH = 8`). `utils.get_citation_ids` recovers keys by the regex `\bpqac-[a-zA-Z0-9]{8}\b`. The key is therefore a *hash of the summary text*, not of the source span. **Observed.**
- `types.py::PQASession.used_contexts` = `{c.id for c in self.contexts if c.id in self.raw_answer}`. Plain containment of a key in the answer string. **Observed — this is the entire "is this citation used" mechanism.**
- `types.py::PQASession.populate_formatted_answers_and_bib_from_raw_answer` computes `set(included_keys) - set(id_to_name_map)` and replaces those with `""`, under the comment "strip out any leftover hallucinated citations." **Observed:** hallucinated *keys* are removed; a *real* key attached to an unsupported sentence is not detected.
- `docs.py` lines 648–652: when the serialized context is shorter than `prompts.EMPTY_CONTEXTS`, the answer is hard-set to `f"{CANNOT_ANSWER_PHRASE} this question due to …"`, where `prompts.CANNOT_ANSWER_PHRASE = "I cannot answer"` and `EMPTY_CONTEXTS = len(CONTEXT_OUTER_PROMPT.format(context_str="", valid_keys="").strip())`. **Observed: this is a deterministic, rule-based abstention — the strongest honesty mechanism in the project, and the direct ancestor of requirement I5 below.**
- `core.py` line 358, `strip_citations` (`utils.py:127`): before a summary is handed to the answer LLM, citation-shaped text is stripped so the summarizer cannot mint its own `pqac-` keys. **Observed.**
- `readers.py::_make_chunk` builds `Text.name` as `f"{doc.docname} pages {name}"`; fixed-size chunking uses `f"{doc.docname} chunk {i + 1}"`; line chunking uses `f"{doc.docname} lines {last_line_i}-{line_i}"`. **Observed: locators are human-readable strings, not structured addresses.**

**Tests inspected:** `tests/test_paperqa.py::test_pqa_context_id_parsing` (parametrized; asserts that hallucinated keys such as `pqac-1234567e` are dropped while real keys survive, and that nested/malformed parentheticals are handled) and `tests/test_paperqa.py::test_unrelated_context` (parametrized with `id="default-unsure"` / `id="custom-unsure"`; asserts the `CANNOT_ANSWER_PHRASE` path fires for unrelated context).

**Inferred, not observed (flagged as inference):** that the project's authors regard C1 as the only citation guarantee they owe. This is inferred from the absence of any quote-diff or numeric-reconciliation code path in `src/paperqa/`, not from a stated design intent.

- **License obligations:** root `LICENSE` is **Apache-2.0**. `packages/paper-qa-docling/LICENSE`, `packages/paper-qa-nemotron/LICENSE`, `packages/paper-qa-pypdf/LICENSE` are **Apache-2.0**. `packages/paper-qa-pymupdf/LICENSE` is **GNU Affero General Public License v3** — verified by reading its first lines, not by inference. See "License obligations" below.

### paperspine

- **Repository URL:** https://github.com/WUBING2023/PaperSpine
- **Exact commit SHA:** `42312b8d9c76ab25990cddfd76e3622276854118` (verified)
- **Inspected paths:** `src/scripts/scientific_evidence_check.py`, `src/scripts/evidence_grounded_review.py`, `src/scripts/citation_verification_en.py`, `src/scripts/citation_bank_check.py`, `src/scripts/results_validation_check.py`, `src/scripts/material_inventory.py`, `tests/test_evidence_grounded_review.py`, `tests/test_readiness_gates.py`, `LICENSE`, `CLAUDE.md` (read as untrusted data, for the safety finding only).

**What was actually observed (not assumed):**

- `scientific_evidence_check.py::GROUP_PREFIXES` partitions a ledger into `sources`(S), `claims`(C), `numeric_facts`(N), `methods`(M), `outcomes`(O), `results`(R); `ID_PATTERN = ^[SCNMOR]\d{3,}$`. `FINAL_STATES = {"verified", "user_authoritative", "not_applicable"}`; `PLANNING_STATES` adds `planned` and `unverified`. **Observed.**
- Same file, `validate()`: `verified` **requires a non-empty `verified_by`**; `user_authoritative` **requires a non-empty `evidence_locator`**; `sources`, `numeric_facts`, `methods` and `results` must *declare* a state at all. Cross-references are checked for existence and for correct group prefix. Claims must have non-empty `text` **and** non-empty `boundary`; results must link ≥1 claim, method and outcome, and must carry a non-empty `uncertainty` note. Exit code is `0`/`1`. **Observed.**
- **Critically: that same `validate()` never reads a source file.** It does not confirm the source exists, does not check that a quoted span appears, and does not reconcile a number. It is graph-integrity validation only. **Observed.**
- `evidence_grounded_review.py` module docstring: "It deliberately contains no provider SDK and **never treats a failed search as a negative result**." **Observed** — this is the strongest stated honesty principle found in either project.
- Same file, `_validate_paper_evidence`: anchor `kind` ∈ `{quote, figure, table, equation, absence_scan}`; `locator` must match `PRECISE_LOCATOR_RE`, which requires an actual page/line/paragraph/figure/table/equation/supplement/appendix coordinate (regex at lines 31–36, and it also accepts the Chinese forms `页`/`行`/`段`/`图`/`表`/`附录`). `source_sha256` must equal `manuscript.sha256`. A positive anchor requires a non-empty `quote`. An `absence_scan` instead requires `search_scope` + non-empty `search_terms` + a `receipt_id` resolving to a scan receipt. **Observed: the locator is a hard, testable gate.**
- Same file, `_validate_tool_receipts`: `TOOL_STATUSES = {completed, partial, no_hit, provider_failure, not_started}`; a `paper_search` with `status == "no_hit"` must record `result_count == 0`; `provider_failure` must record an `error`. **Observed: "found nothing" and "could not look" are separate, and conflating them is an error.**
- Same file, lines 243–247: `usage.telemetry_status` ∈ {`measured`, `unavailable`}; when `unavailable` it increments `telemetry_unavailable_count` and appends the warning "zero values are not measured cost." **Observed: an unknown quantity is disclosed as unknown rather than recorded as zero.**
- `citation_verification_en.py`: queries the public Crossref REST API to confirm a cited work exists, then `_titles_similar` (substring of first 40 chars, else `difflib.SequenceMatcher` ratio ≥ `MIN_TITLE_SIMILARITY = 0.6`) and `_years_close` (`abs(ly - cy) <= YEAR_TOLERANCE = 1`). **Observed: this is C1 against a bibliographic registry. It never fetches or reads the cited work's content, so it cannot do C2.** Two observed fail-open behaviors: `_years_close` returns `True` when either year is absent (comment: "can't judge, be permissive"), and an unreachable Crossref API marks entries `skipped`/`warning` rather than failing.
- `results_validation_check.py::validate`: each results row must have a non-empty `Contribution Claim Tested` and a non-empty `Result/Evidence` — the comment states a metric-only row "proves nothing about what the paper claimed." Empty `Allowed Interpretation` / `Interpretation NOT Allowed` cells are **warnings**, not failures. **Observed: the existence of the mapping is enforced; the correctness of the interpretation is explicitly out of scope.**
- `material_inventory.py::InventoryItem` fields are `path`, `extension`, `file_type`, `role_hint`, `size_bytes`, `mtime_ns`, `mtime_utc`. **Observed: no content hash and no locator — shallower than LC-P1-08 requires.**
- No numeric reconciliation against source data was found anywhere in `src/scripts/`; every numeric operation there is text-similarity scoring (Jaccard / `SequenceMatcher` in `_paper_spine_utils.py:154`, `citation_quality_audit.py:295`). **Observed.**

**Tests inspected:** `tests/test_evidence_grounded_review.py::test_unlocated_comment_cannot_pass`, `::test_provider_failure_cannot_support_major_novelty_blocker`, `::test_no_hit_requires_zero_results_and_is_not_provider_failure`, `::test_unavailable_telemetry_is_disclosed_not_counted_as_measured`, `::test_valid_strict_contract_is_hash_bound_and_costed`; `tests/test_readiness_gates.py::test_final_ledger_passes_when_links_and_states_are_explicit` and `::test_final_ledger_rejects_unverified_result`; `tests/test_citation_verification_en.py::test_resolvable_doi_with_year_mismatch_is_matched_not_failed`.

**Inferred, not observed:** that the PaperSpine authors regard scientific interpretation as inherently outside machine-checkable scope. Inferred from `results_validation_check.py` demoting interpretation cells to warnings while promoting link-existence to failures; not stated outright.

- **License obligations:** root `LICENSE` is **MIT** ("Copyright (c) 2026 PaperSpine contributors"), observed at the pinned SHA.

### License obligations — the AGPL subpackage

`packages/paper-qa-pymupdf/` in paper-qa is **GNU AGPL v3**. This was confirmed by reading the header of `packages/paper-qa-pymupdf/LICENSE`; it is not inferred from repository metadata.

**Handling conclusion for this ADR:**

1. **No AGPL code is copied, adapted, translated, or structurally mirrored into LabCairn.** This holds in both directions: not into the implementation, and not into the documentation.
2. **No design conclusion in this ADR is sourced from `packages/paper-qa-pymupdf/`.** Every paper-qa finding above cites only `src/paperqa/`, which is covered by the root Apache-2.0 license. The AGPL subpackage was opened only to read its license header. LC-P1-08's page/span locator design will be derived from `docs/PHASE_1_WORKORDERS.md` (which already specifies "text PDFs (PyMuPDF, page and span)") and from PaperSpine's MIT-licensed `PRECISE_LOCATOR_RE` idea — both independent of the AGPL package.
3. **This also removes a latent dependency trap.** That subpackage is precisely the PDF-parsing layer a retrieval-layer adoption (A1) would have pulled in. Rejecting A1 is what keeps an AGPL-licensed component out of LabCairn's dependency graph, so the rejection and the license finding reinforce each other.
4. `docs/UPSTREAM_REFERENCES.md` already warns that "a GitHub-public repo is not automatically permissively licensed." This is the concrete instance: the root license line in that catalog's table is accurate for the root and misleading for one subdirectory. The G5 license audit should assert subpackage licenses explicitly, not just root.
5. **Should a future need arise to consult that subpackage**, it is read-only design study, gated on a fresh license review, and any conclusion drawn from it must be re-derived from an Apache-2.0 or MIT source before it can influence LabCairn code. This ADR records that constraint so it is not rediscovered under time pressure.

## Decision and why this fits LabCairn

**Decision:** LabCairn defines its own evidence model from first principles, adopting *no* upstream code. It takes three ideas from paper-qa and five from paperspine, all reimplemented independently (see Contracts). It rejects both projects as dependencies.

The fit is direct:

- `docs/ARCHITECTURE.md` makes SQLite the canonical authority and requires that "Conversation text is neither the task state nor scientific evidence by itself." A paper-qa-shaped LLM-summary ledger violates this by construction; a PaperSpine-shaped Markdown artifact set is not transactional. LabCairn's ledger must be application-owned rows, not model output.
- LC-P1-09 mandates C1–C4 as four distinct checks. Neither upstream provides them: paper-qa provides C1 only and only weakly; paperspine provides a strong C1 against Crossref (which needs network, against a local-first product) plus a strong *structural* integrity check that is not any of C1–C4. The gap is the design work, and it has to be LabCairn's own.
- The single most important decision here is negative: **C4 has no implementation in Phase 1.** PaperSpine already models this, if informally — `results_validation_check.py` makes "is this interpretation scientifically warranted" a *warning* while making "does this row link to a claim and a result" a hard *finding*. LabCairn promotes that asymmetry from a convention into a typed contract: `check_scientific_interpretation` exists, has a signature, and **always returns `not_checked`**. It is never absent (so callers must handle it) and never green (so callers cannot be misled).

This gives a defensible ceiling: LabCairn can prove a number came from a cell, and that a quote came from a page. It cannot prove that the inference drawn from them is sound, and the system will say so on every record.

## Risks, tradeoffs and reversibility

**R1 — Six states are more machinery than a typical MVP needs.** Mitigation: the state machine is deliberately small (six states, transitions below), stored as a column with a check constraint, and the report layer only needs to *display* it. Accepted knowingly: collapsing states would lose exactly the cases LC-P1-09's acceptance list names.

**R2 — C2 will produce false negatives on legitimately normalized text.** A PDF reflow, a ligature, or a Unicode normalization difference can break verbatim matching. Mitigation: C2 returns three outcomes (`pass` / `fail` / `indeterminate`), not two. `indeterminate` routes to `user_attested`, never to automatic failure and never to automatic pass. A strict-by-default matcher would train users to disable it.

**R3 — No C4 means reports will be visibly incomplete.** This is intended, not a defect. Every scientific interpretation must carry a visible marker. Risk is a user reading `verified_by_rule` and inferring endorsement; mitigation is that the *rendered* label never uses the word "verified" alone.

**R4 — Upstream re-implementation drift.** LabCairn's ledger will not track either project. Accepted: these are different products with different goals, and coupling would import paper-qa's summary-centric retrieval.

**R5 — The retrieval/evidence split may not survive contact.** If FTS5 lexical retrieval proves too weak for ground-truth queries (LC-P1-09 acceptance), the honest outcome is a disclosed recall failure, not a silent switch to embeddings whose summaries cannot support C2.

**Reversibility:** high. No upstream code is copied, so there is nothing to unwind. The state enum, the record schema and the validator interfaces are LabCairn-owned and can be revised by a superseding ADR. The one expensive-to-reverse choice is naming `evidence/` as application-owned SQLite rather than an artifact directory — but that is required by the architecture baseline and is already covered by Alembic migrations.

## Contracts and acceptance tests

### Contract 1 — `EvidenceRecord`

LabCairn-owned, Pydantic v2, versioned, persisted in `src/labcairn/evidence/`. Not copied from any upstream schema.

```python
class VerificationStatus(StrEnum):
    PLANNED          = "planned"
    EXTRACTED        = "extracted"
    VERIFIED_BY_RULE = "verified_by_rule"
    USER_ATTESTED    = "user_attested"
    CONFLICTED       = "conflicted"
    UNSUPPORTED      = "unsupported"

class EvidenceKind(StrEnum):
    CLAIM  = "claim"
    NUMERIC = "numeric"
    RESULT = "result"

class EvidenceRecord(BaseModel):
    evidence_id: str                 # stable, generated
    schema_version: int
    task_id: str
    kind: EvidenceKind

    text: str                        # the claim as written, for CLAIM/RESULT
    value: float | None = None       # for NUMERIC
    unit: str | None = None          # for NUMERIC; must be declared, not inferred

    anchor_ids: list[str] = []       # -> SourceAnchor.id
    extracted_span: str | None        # the literal text copied out of the source
    extracted_span_sha256: str | None

    status: VerificationStatus
    verification_log: list[VerificationRecord]   # append-only, never rewritten

    # provenance: who/what produced this state, and from which content
    created_by: Literal["rule", "user", "model_proposal"]
    created_by_id: str               # rule id, user id, or model run id
    source_content_hash: str | None  # hash of the source as read at extraction
    created_at: datetime
    superseded_by: str | None = None
```

`VerificationRecord` (appended to `verification_log`) records `check` (which of C1–C4), `checker_id`, `outcome` (`pass` | `fail` | `indeterminate` | `not_checked`), `detail`, `checked_at`. `docs/ARCHITECTURE.md`'s "Verification records include what was actually checked" is implemented by this table, not by the status column.

### Contract 2 — state machine transition conditions

| From | To | Required preconditions |
|---|---|---|
| `planned` | `extracted` | ≥1 `anchor_id` resolving under C1; `extracted_span` and `extracted_span_sha256` both non-empty; `source_content_hash` recorded |
| `extracted` | `verified_by_rule` | ≥1 `VerificationRecord` with `check` ∈ {C1, C2, C3}, `outcome == pass`, from a `checker_id` present in the registered rule catalog |
| `extracted` | `user_attested` | `created_by == "user"`, a non-empty user identity, and the attestation action logged |
| `extracted` | `conflicted` | ≥2 records of the same `kind` on the same claim/numeric key whose C3 verdicts disagree beyond the declared tolerance |
| `extracted` | `unsupported` | C2 `fail`, or C1 `fail`, or C3 `fail`, or no anchor at all |
| any | `conflicted` | as above; conflict is not a terminal failure but a state that must be surfaced |
| any | `unsupported` | evidence cannot be located or does not support the record |

Hard invariants:

- **I1.** `verified_by_rule` and `user_attested` are mutually exclusive endpoints. Neither transitions to the other; a change of mind goes back through `extracted`.
- **I2.** There is **no state meaning "scientifically established."** `not_checked` from C4 is the permanent terminal for interpretation, and the enumeration must not grow a seventh member in Phase 1.
- **I3.** A status may never be upgraded without appending a `VerificationRecord`. Status without a log entry is a schema violation, caught by a DB check.
- **I4.** If `source_content_hash` no longer matches the source, the record is **invalidated** — not silently refreshed — and downstream artifacts are marked stale (ties to LC-P1-06).

### Contract 3 — the four cite-support validator interfaces

Four independent callables in `src/labcairn/evidence/cite_support/`. Each returns a verdict object; none may raise past its boundary. **`indeterminate` and `not_checked` are never equal to `pass`.**

```python
# C1 — does the source exist and does the locator resolve?
def check_source_exists(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Resolve every anchor_id against the ingested material; re-verify the
    recorded content hash. Returns pass if all anchors resolve and hashes match,
    fail if an anchor id is unknown or the locator does not resolve, and
    indeterminate if the material is present but is a format LabCairn cannot
    address (e.g. a scanned PDF with no OCR)."""

# C2 — is the quoted text actually there, verbatim?
def check_quotation_support(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Match record.extracted_span against the text at each anchor's located
    span, under a declared normalization profile. pass = exact match after
    normalization. fail = the located span was resolved and does not contain it.
    indeterminate = resolved but normalization made the comparison unreliable.
    Never fuzzy-matches into a pass."""

# C3 — does the number agree with the anchored data?
def check_numeric_consistency(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Re-read the anchored cell/segment and compare to record.value under the
    declared unit and tolerance. fail on unit mismatch or on a difference
    exceeding tolerance. indeterminate when the segment is non-numeric or
    the declared tolerance is absent — an undeclared tolerance is never 0."""

# C4 — is the scientific interpretation warranted? (NOT IMPLEMENTED, PHASE 1)
def check_scientific_interpretation(record: EvidenceRecord) -> Verdict:
    """Phase 1: this function has a body and always returns not_checked.

    It exists so that every call site is forced to handle the
    unverified-interpretation case. It must never return pass, and must not
    be deleted — removing it would let callers silently stop handling C4.
    Extending it is a separate ADR with its own evidence standard.
    """
    return Verdict(outcome="not_checked", checker_id="c4.not_implemented",
                   detail="Scientific interpretation is not machine-verifiable "
                          "in Phase 1. Do not present this record as "
                          "scientifically established.")
```

The C4 signature is the load-bearing part: callers must handle `not_checked`, so a record whose interpretation was never checked cannot be displayed as though it had been.

### Contract 4 — when the system must say "I don't know"

Each item is a testable acceptance condition, not a guideline.

- **A1 — Unresolvable locator.** Given an `anchor_id` whose locator does not resolve against ingested material, C1 returns `fail` and the record is set `unsupported`. *Test:* a `SourceAnchor` pointing at page 99 of a 3-page PDF fails; the report cites nothing rather than falling back to the nearest page.
- **A2 — Hash drift.** Given a source whose bytes changed after anchoring, C1 returns `fail`, the record is invalidated per I4, and every artifact derived from it is marked stale. *Test:* modify a fixture PDF after extraction; downstream artifact is stale.
- **A3 — Quotation mismatch.** Given an `extracted_span` absent from the located span, C2 returns `fail` and the record cannot become `verified_by_rule`. *Test:* a paraphrase presented as a quote does not reach `verified_by_rule`.
- **A4 — Ambiguous quotation.** Given normalization uncertainty (ligatures, reflow, hyphenation), C2 returns `indeterminate`. *Test:* such a record is routed to `user_attested` only, and never auto-promotes. **`indeterminate` must never be reported as pass.**
- **A5 — Conflicting numbers.** Given two records for the same numeric key with differing C3 verdicts beyond tolerance, both become `conflicted`. *Test:* neither wins by recency; the conflict is displayed.
- **A6 — Empty retrieval.** Given a query returning zero excerpts above threshold, retrieval returns an explicit *no evidence found* result. *Test:* the flow does not call the model with empty evidence and does not produce an answer. This is the direct descendant of paper-qa's `docs.py:649` `EMPTY_CONTEXTS` check and of PaperSpine's `no_hit` vs `provider_failure` split.
- **A7 — Unreadable source.** Given a scanned PDF, ingestion records it as `unreadable` with an explicit "OCR not available" disclosure, excludes it from the FTS5 index, and refuses to cite it. *Test:* an unreadable asset is distinguishable from a file with no matching results — both required by LC-P1-08.
- **A8 — Unknown is not zero.** An unavailable measurement (token usage, timing) is stored as unknown and disclosed as unknown, never as `0`. *Test:* `telemetry_status`-style disclosure, reimplemented independently from PaperSpine's `_validate_tool_receipts` warning.
- **A9 — Failed search is not a negative result.** A provider or index failure is never recorded as "searched and found nothing." *Test:* `provider_failure` and `no_hit` remain distinct; a failure cannot discharge an evidence requirement.
- **A10 — Interpretation is always unverified.** Every `CLAIM` or `RESULT` record rendered into a report displays an explicit "interpretation not machine-verified" marker, because C4 returned `not_checked`. *Test:* the marker is present on every such record and absent from nothing that claims C4 support.
- **A11 — Retrieved text is data.** Excerpt text entering a model context is wrapped so it cannot alter capabilities, per `docs/ARCHITECTURE.md`. *Test:* an excerpt containing instruction-shaped text does not change tool availability or permissions.
- **A12 — Fabricated source fails.** A record whose `source_ids` name a source absent from the ledger fails C1. *Test:* a fabricated DOI/source does not pass the final gate — the LC-P1-09 acceptance case.

## Re-evaluation trigger

Revisit this ADR when any of the following occurs:

1. G3 review finds that C2 `indeterminate` occurs so often that the state machine is unusable in practice — revisit the normalization profile, not the six states.
2. A proposal appears to implement C4. That requires its own ADR with an independent evidence standard; the default stays `not_checked`.
3. LC-P1-10's reproducibility manifest is designed — the manifest and `EvidenceRecord` must share a single hash lineage, and that alignment may change `source_content_hash`'s definition.
4. `packages/paper-qa-pymupdf/`'s license changes upstream at a SHA we re-pin, or a PDF-parsing need appears that the Apache-2.0 subpackages cannot serve. Either reopens a license review; neither silently reopens A1.
5. LC-P1-13 evaluation shows retrieval recall is the binding constraint. Any move to embeddings must still return verbatim source spans, or C2 becomes unimplementable — which would be grounds to supersede this ADR rather than amend it.
6. The six-state enumeration is proposed for extension. Per I2, adding a "scientifically established" state is not an extension; it is a different product and needs its own gate.

## Safety note on upstream material

Per LC-P1-00 item 5, all upstream files were treated as untrusted reference data. Nothing under `E:/labcairn-upstreams/` was executed: no `pip install`, no test run, no entrypoint, and neither `install.sh` nor `install.ps1` from paperspine was run or sourced. No upstream source was copied into this repository. One instruction-shaped artifact was encountered and deliberately **not** followed — recorded in the delivery report rather than acted upon.
