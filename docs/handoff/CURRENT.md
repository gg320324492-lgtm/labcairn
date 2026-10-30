# LabCairn — Current handoff

**Date:** 2026-10-31 · **Branch:** `claude/p2-lc-p2-10-plans` — LC-P2-10's
T00–T06: the label set, the annotation guide, the synthetic corpus and its
manifest, the agreement, the manifest's refusals, the acceptance record and
the shard costs, **and the annotations themselves**. **`main` is
`da470bb`** — the merge of PR #132, LC-P2-02 — **and this branch is
twenty-three commits ahead of it, every one of them LC-P2-10's.**
**Nothing of this round was pushed and no new pull request was opened**,
because a CI run is spent on a whole body of work rather than on each piece
of it, and that is the owner's call. PR #133 carries the work and is green.

**The full suite has not been measured as one run on the final tree, and
the reason is the machine, not the tree.** Two overnight attempts ended in
the same fingerprint — `0xC0000142`, Windows refusing to start a new
process, while this machine's nonpaged pool stands at 6.72 GB with 453
processes (a known driver leak; only a restart clears it). The judgement,
its five pieces of evidence and the chain that stands instead are in
`docs/acceptance/LC-P2-10-acceptance.md` §5; after a restart, one command
re-measures it: the project's temp rules, then `pytest` with a basetemp
outside the repository.

**What landed.** `src/labcairn/papers/labels.py` (the closed vocabulary),
`src/labcairn/papers/gold_manifest.py` (the manifest's one contract, with
**two verdicts** — well formed, and finished), `docs/papers/annotation-guide.md`
(every label with a worked example and a boundary case),
`docs/papers/gold-set-manifest.json` and `tests/fixtures/papers-gold/`
(**four manuscripts, two projects, two partitions, ten comments**),
`tests/test_gold_set_labels.py`, `tests/test_gold_set_agreement.py`,
`tests/test_gold_set_manifest.py` and `tests/test_gold_set_corpus.py` —
**forty-eight witnesses** — every one of them re-checked by a mutation that
had to turn that witness red — and
[`acceptance/LC-P2-10-acceptance.md`](../acceptance/LC-P2-10-acceptance.md).

**Five things the round found, and they are worth more than the code.**

- **The breakdown's premise about the issue kinds was wrong, and wrong
  invisibly.** It read *"the issue kinds are LC-P2-09's"* — and LC-P2-09 has
  no issue kinds: it has `issue_key`, a free-text key a person gives, which
  the chain refuses to infer because the same wording is not the same issue.
  **A key somebody types is not a vocabulary somebody can choose from.** The
  real source is in the tree — the upstream study's own quotation of the
  design's twelve — and the label set is now **tied to that document**: the
  witness reads the set out of it, so a change to the vocabulary that nobody
  recorded fails the test rather than passing it.
- **The agreement's denominator cannot be told from the manifest's item
  count by its number.** The manifest requires two readings per item, so over
  any manifest the function accepts, the two counts are equal. The witness
  pins the number, the words that name what it counted, and the refusal to
  compute over a manifest with one reading — and the record says plainly
  that the fourth thing it cannot pin is the fourth.
- **The Ubuntu shard partition is outside the balance limit, and that is
  structural.** `tests/test_cli.py` costs 278 seconds of a 959-second suite,
  so the best factor five shards can reach is `278 / (681 / 4) = 1.634`, and
  the partition is already at that floor. The cost check's slack came out
  negative, so it reported **every** changed file as one that could unbalance
  the partition — a quarter-second test file, named as the reason a partition
  is lopsided. The check now asks whether the changed file is the bottleneck,
  and two witnesses hold that reading down. **A partition inside the limit
  needs a different number of shards or a cheaper `test_cli.py`, and both are
  the owner's call.**
- **A key that names its issue hands the reader the answer, and one did.**
  The manifest's `issue_key` was a value that says the issue kind before
  anyone reads the manuscript. **All three annotation sessions read the
  manifest**, and the transcripts were searched for the moment that wording
  entered each one: it was in A's and B's context **before either wrote its
  labels**, and in the arbiter's only afterwards. B's own notes say it used
  the key. **So four of the sixty labels were made with the answer in
  reach**, and the record says so rather than reporting 60/60 as if every
  label had been read blind. The key is now opaque, the guide has a section
  on which fields not to read before labelling, and **a blind-read audit —
  a fourth session given only the manuscripts and the guide — is the
  measurement that turns "the hint did not change the labels" into a
  number.** It agreed with both readings on **all twenty issue kinds**,
  **and it found the leak was still open in the guide's §1.0.1** — the one
  section every annotator reads first. **That text no longer quotes the
  retired name**, and the retired name is now written down only in the
  acceptance record, where it is evidence rather than a hint.
  **The pair was then read again by a session that had never seen that
  name**, and it gave both items the same label the manifest's three
  readers gave — **so all twenty issue-kind labels now have a measured
  independent agreement.** **And those readings are in the tree**
  (`docs/papers/gold-set-blind-readings.json`) with two witnesses over
  them: one that every label they carry is the label the manifest's own
  readers gave, and one that the record carries no `issue_key` and names
  none of the manifest's readers — **a record of somebody's blindness
  that names what they were blind to is not a record of blindness.**
- **The manifest refused two readings by one annotator, and said nothing
  about the arbiter.** So a manifest whose arbiter *was* one of its own
  annotators was accepted — **and an arbiter who is one of the two has
  read the item twice rather than arbitrated it**, and the agreement
  number over that item would be a statement about one reader. The
  contract now refuses it by name, and two witnesses watch it: one for
  the rule and one for the tree's own manifest, so neither can cover for
  the other.

**What this round does not do:** **T06's readings were made by Claude
sessions, not by people** — the manifest's ids say so (`agent-annotator-a`,
`agent-annotator-b`, `agent-arbiter-1`), because an id that does not say
what it is will be read as a person. **Two of the six agreement views are
degenerate**: the corpus holds no assessment record, so `assessment_outcome`
is `unknown` on all twenty readings and its two views are 10/10 by default
rather than by judgement. **The external readings cover the issue-kind
axis only**, so the other two axes are backed by the two annotators and
the arbiter and by nothing else. The four new test files' shard costs are
**apportioned rather than measured on a runner**, and the first CI run after
this lands will give better numbers.

**Date:** 2026-10-30 · **`main`:** `76d25ca` — the merge of PR #130, which is
LC-P2-09 · **Previous `main`:** `503b5fe` (PR #129, LC-P2-06's review and its
seven findings).

**LC-P2-09 is merged and measured, and not independently reviewed.**
The feedback chain's four tables (`0013_feedback_chain.py`), the version
graph's missing writer (`0012_version_edge_rejections.py`), the reader
carrying the text a comment covers, and the four annotation events are in
`main`; the acceptance record is
[`acceptance/LC-P2-09-acceptance.md`](../acceptance/LC-P2-09-acceptance.md),
and the review points are in
[`plans/PHASE_2-review-points.md`](../plans/PHASE_2-review-points.md).

**Two things about this round are worth knowing before reading it.**

- **The chain's events existed and nothing emitted them** — `T05` landed the
  payload models and the four `emit_*` functions, and no operation called
  one. The four `record_*` operations now write the row and the event in
  one unit of work, and `examples/feedback_demo.py` reads the stream back.
- **Two branches claimed migration `0012`.** The version graph's rejection
  table kept the number; the chain's four tables became `0013`.

**What this round does not do:** the mutation pass covers six of eighteen
review-point properties; the review is not independent; the chain is not
rendered (ADR-0017's first re-evaluation trigger); and the product still has
no writer for grants. Those are stated in the acceptance record, §6.

**Date:** 2026-10-29 · **Previous `main`:** `6db48ef` — the merge of PR #124, and
the last of the Phase 1 closeout merges. **What landed since `ff9afc5`:** PR #119
(a claim recorded by the product's own operation, the reconciled event readable by
a process that never imported the writer, and **the paid probe made runnable** —
the smoke test that hard-coded a protocol and passed `environ={}` could never
have run on any machine; it now reads four variables, ran three times against a
real endpoint, and `.github/workflows/provider-smoke.yml` holds the gate class
the required checks will never carry), PR #120 (the approval-store wiring scoped
to Phase 2, with its schema cost named), PR #121 (the owner's closeout rulings
recorded), PR #122 (**§1.4.1b is now the harness's behaviour**: a skip whose
reason names a fact of the machine no longer fails a blocker, any other skip
does, and accepted ones are named in the row — plus the two defects that
surfaced while reading the tree to check it: class-based cases were keyed to
files that do not exist, costing a metric 48 of its 82 witness cases, and three
files in the CI shard list collect no test at all), PR #123 (the board naming the
commit that review was made at), and PR #124 (the **G1/G2 human-review
checklist**, prepared and not executed, with a witness that resolves every node
id it cites). **Every Phase 1 owner question the records put to the owner now has
a ruling written against it** — §1.4.2 on 2026-10-28, and §1.4.1b, §1.4.1 and
§1.4.3 on 2026-10-29, all four in the board's ruling block. **What those rulings
do not close** is the fact behind §1.4.1: who holds the copyright is outside this
repository, and "no licence declared" leaves the ownership exactly as open as it
was — the ruling closes the question *what do we claim*, not the question *what do
we own*. The human pair of eyes G1 and G2 still owe the board likewise has a
checklist and no reviewer.
The first Phase 2 work-order list is drafted at
[`plans/PHASE_2-work-orders-draft.md`](../plans/PHASE_2-work-orders-draft.md).

**Date:** 2026-10-27 · **Previous `main`:** `ff9afc5e8a50cf64cb5a5fdf7edaf8d32c60d776` — the merge of
PR #118 (`delivery/g5`), which carries **G5's own findings fixed and each fix
watched** (S1–S6) and the two reviewers' re-verifications. G5's review subject
was `72154cd` (PR #116, the gate's delivery) and `3852cde` (PR #117, the first
review's findings); the gate's record is
[`acceptance/G5-acceptance.md`](../acceptance/G5-acceptance.md).

**Phase 1's board is complete on its own terms:** every work order
LC-P1-00 … LC-P1-14 is `PASS` or `PASS WITH NOTES`, and all six gates say
closed. **What Phase 1 does not deliver is stated in
[`RELEASE-NOTES.md`](../RELEASE-NOTES.md) §2**, and the two biggest items there
are that no task path calls a model, and that the report and the figure have no
surface entry point.

**Date:** 2026-10-25 · **Previous `main`:** `d49ec323eb52c6515e45dbc9c1933243056f926f` — the merge that carries
G4's follow-ups: the tests copy a migrated database instead of migrating one
each time, the DOCX's font claim is watched, the earlier gates' exit
demonstrations are run by a test, the font licence audit is measured, and the
CI runs in six shards per platform (34.5 minutes → 7.3).

**Date:** 2026-10-23 · **Earlier `main`:** `e8a63a813ad26d0dfca06dc672442e5dd3e66812` — the merge that closes G4. The gate's own review was at `9381036af0104172f16fe94a6edd2e8cb6d9ae04`, the commit the review measured, which is the merge's second parent. The merges since the previous refresh are #87 (every subprocess in the packaging test now has a ceiling), #88 (the doctor finds the session token, and the service lets go of the store), #89 (**`labcairn serve`**, the command that starts the local API service), #90 (the escape table holds eighteen characters), #91 (the service gives every request a session of its own), #92 (the report's material, the Markdown's whitespace, and the refusals nobody watched), #93 (the ingestion operation: the layer can read the material, and the CLI can bind it), #94 (the walk records where the material is, not the key it was handed), #95 (the material's one source, and the numbers in all four forms), #96 (the four forms are compared with the document they are drawn from), #101 (the demonstration's approval outlives the grant, at any hour — the gate's exit test had a time bomb in it, and no CI run had ever run after 13:00 UTC), #106 (the batch: **the two blockers and the six notes** the three surfaces' independent review found — among them the demonstration's **exit code** was not load-bearing, and a stage run that followed an approval **planned a second operation** — plus the **five defects the fixing found**, one of them an **authorisation bypass**, one of them a **time bomb in the gate's own exit demonstration**, and one of them a duplicated sentence in that demonstration's own output) and #108 (the working rules, written down where a session will read them).

**This file rots on every merge and no test can catch it.** `tests/test_status_consistency.py` checks that the gate table agrees with the plan, that every status is from the declared vocabulary, that a row claiming progress cites evidence, and that relative links resolve — but "how far along is the work" is a semantic judgement, not a parseable fact. This file was **six merges stale** when it was last checked: it named PR #24 as current and claimed no material parsing existed, which stopped being true at #25. It was then stale again at #32, and the claim it made — "Nothing is implemented" for LC-P1-09 — stopped being true at #33. **Thirteen merges passed with no refresh; this is the first refresh in thirteen merges** — the file named `8fb9f18` (PR #68) as current, and the claim it made — "**No research capability yet.** There is no CLI, no server, no web UI" — stopped being true at #73 (the local FastAPI service), #76 (the Typer CLI) and #80 (the React workbench). Refresh it in the PR that reports the change, and check `git log origin/main` rather than trusting it.

## Gates

| Gate | Status |
|---|---|
| G0 | **closed** — LC-P1-00 PASS WITH NOTES, subject `623e3ca` |
| G1 | **closed** — LC-P1-01, LC-P1-02, LC-P1-03 and LC-P1-04 all PASS WITH NOTES (the board and `G1-evidence.md:9` agree; LC-P1-02/04 were corrected from a bare `PASS` on 2026-10-28 to match their own evidence) |
| **G2** | **closed** — LC-P1-05/06/07 all PASS WITH NOTES. [Acceptance](../acceptance/G2-acceptance.md) · [narrative record](../acceptance/G2-evidence.md) |
| **G3** | **closed** — LC-P1-08, LC-P1-09 and LC-P1-10 all PASS WITH NOTES, and the gate closed on an **independent review** at `d114810` (verdict PASS WITH NOTES; every one of the gate's fourteen fixes broken, no mutation survived). [Acceptance](../acceptance/G3-acceptance.md) |
| **G5** | **closed** — LC-P1-13 and LC-P1-14 both `PASS WITH NOTES`, and the gate closed on **two independent reviews** that wrote **none** of its fixes: the product-and-measurement scope's first verdict was **FAIL** on a clean property table, and after its findings were fixed **it re-ran its own eleven mutations against the fixed code and passed**; the documents-and-release scope's verdict is **PASS WITH NOTES**, with every one of its fourteen re-run by the reviewer that wrote them. **Twenty-four findings between them, all fixed.** The gate also found six of its own, and its own end-to-end test found one more — the surfaces never run the recovery pass — which is **handed over rather than fixed**. **Closed since the gate**, in the section below. [G5 acceptance](../acceptance/G5-acceptance.md) · [the first review](../acceptance/g5-review-product.md) · [the second](../acceptance/g5-review-records.md) |
| **G4** | **closed** — LC-P1-11 and LC-P1-12 both `PASS WITH NOTES`, and the gate closed on an **independent review** at `9381036af0104172f16fe94a6edd2e8cb6d9ae04` (verdict **PASS WITH NOTES**; two reviewers who wrote none of the gate's fixes, one per scope — the report path's review **failed the gate five times** on a clean property table, and the three surfaces' review came back **BLOCKED five times and FAIL once**, the first on two blockers and six notes, one of the blockers sitting directly under the gate's own exit test, and the last, at `47259e0`, on **this round's four findings** — the shared rule's own witness, one command-level refusal, the pairing by value, and the crash fix's two catches — **were fixed, and the review re-verified its own findings against the fixed code and passed**. [G4 acceptance](../acceptance/G4-acceptance.md) · [LC-P1-11 acceptance](../acceptance/LC-P1-11-acceptance.md) · [LC-P1-12 acceptance](../acceptance/LC-P1-12-acceptance.md) |

## What exists now

The engineering floor from G2: versioned contracts, provider adapters with fail-closed budgets, workspace permissions, a SQLite task store with transactional events, crash recovery that enters UNCERTAIN rather than guessing, and the `research-report` Skill contract.

And, from LC-P1-08: **material ingestion works end to end.** Text, Markdown, CSV, XLSX and PDF adapters produce text units with locators — page, line, row+header, sheet+cell — which a workspace walk reads through `SourceMaterial` and stores as `sources` rows plus content-addressed `source_texts`, with hashed bytes and workspace-relative paths. Unreadable material is separated from empty material and from readable material, and neither unreadable state is citable.

And, from LC-P1-09: **the ledger has a store, an index, four working checks and a gate.**

- Revision 0005 creates `evidence_records`, `evidence_anchors`, `verification_records` and the `evidence_fts` FTS5 table; 0006 rebuilds that table on a **trigram** tokenizer, and 0007 adds `source_anchors`, the anchor registry.
- Normalisation is an index-side copy with a declared profile and an `alters_letters` flag, so a comparison can report how lossy it was (T02).
- Retrieval works over the real papers: fifteen ground-truth queries, eleven that must find the right pages and four that must find nothing, validated against the PDFs before any index existed (T03).
- The index is built from the store and reports what it excluded (T04).
- **All four cite-support checks answer.** `check_source_exists` resolves every cited anchor and
  compares three separate hashes (T05). `check_quotation_support` walks a ladder of four
  normalisation profiles and refuses to promote a lossy match to `pass` (T06).
  `check_numeric_consistency` re-reads the anchored cell and compares parsed values under a
  declared tolerance (T07). C4 returns `not_checked` and always will.
- **The ledger persists records through a state machine** (T08). `advance` and
  `attest` are the only ways a status changes, and each refusal names the
  Contract 2 rule it refused. A `verified_by_rule` record's passing entry must
  name a checker id in the rule catalog -- the one rule the model cannot
  enforce, because it accepts any id, and a human attestation is logged by a
  human's id.
- **The evidence gate refuses** (T09). It re-runs the checks rather than reading
  their verdicts -- a record whose source has drifted is invalidated, not kept
  with a stale "pass" -- and it refuses as a whole: `citable` is empty when any
  record fails, because a partial list would invite a caller to cite the ones
  that survived. A conflict is handed over as data with two interchangeable
  sides, so the structure itself cannot express a winner.

Both exit demonstrations run green:

```bash
uv run python examples/g2_exit_demo.py      # persist, crash, restart, resume — 14 checks
uv run python examples/g2_uncertain_demo.py # the uncertain path end to end — 18 checks
```

And, from LC-P1-10: **bounded analysis and a deterministic figure.** Seven descriptive operators and a catalogue built from their **own id constants**, so **one id has one spelling**; a grouped aggregate that returns a **table** rather than a number, because there is no "the grouped mean" of three groups, and whose statistic is **composed** from a registered operator rather than reimplemented; a figure's editable source as a JSON recipe of exactly **three** parts — data, encoding, output — with **no script beside it and no way to run one**, which is what makes *"no general-purpose model-authored code execution"* satisfiable rather than aspirational; a **deterministic** renderer, whose controls were **measured** rather than asserted (the SVG's creation date and its salt each shown to matter, PNG shown to need **neither**); and the **reproducibility manifest**, with its six fields and **one hash lineage** — the manifest's input hash, the selection's `content_sha256`, the source's `content_sha256` and the file's bytes are the same value.

And, from LC-P1-11: **the report path.** One `ReportDocument` — the model — with **four renderers** over it (Markdown, HTML, DOCX and PDF), the report artefact manifest, the revisions and the staleness that finds them, **five content checks**, the document builder that assembles what a task actually has (a record that may be stated becomes a claim and one that may not becomes a disclosure), and the application layer's `render_report`, which gathers, builds, checks, renders the four forms **from that document**, writes the revision with the chain as a flat ancestor closure, and records the receipts and the event. Its [acceptance review](../acceptance/LC-P1-11-acceptance.md) is written — verdict **PASS WITH NOTES**, **136 mutations** run against the merged branches, each caught by a **named** test — and **its reviewer's independence is not discharged**: the reviewer specified the work, dispatched the implementation, wrote the fixes and reviewed them.

And, from LC-P1-12: **three surfaces behind one application layer.** The layer the CLI, the local API and the web UI all call (`d114810`), its event read with the cursor that resumes it (`e344a93`), the **Typer CLI** — `init`, `doctor`, `task create/run/status/resume`, `sources inspect`, `artifacts list` (`99c3d49`) — the **local FastAPI service** on 127.0.0.1 with its **three guards** (the bind address, the origin, and the session token) and its typed contract (`60ebe11`), and the **React workbench** (`6c92e41`).

## What does not exist yet

**The report and the figure both gained surfaces since the gate.**
`labcairn task report`, `POST /report` and the workbench's **Render the report**
button all call the layer's own `render_report`; the surfaces answer with its own
`ReportRendered`, and a fresh workspace permits
`report.render` (the registry binds it to output roots). The figure followed it:
`labcairn task figure` and `POST /analysis` call `run_figure` through the same
layer, with `task approval-request` / `task approval-grant` beside them, because
ADR-0012 constraint 7 moved the recipe inside `analysis.run`'s consented
arguments. **The surfaces can give a task a claim to carry now.**
`labcairn task claim` and `POST /claims` call the layer's `record_claim`, and
`labcairn sources addresses` and `GET /sources/{source_id}/addresses` list the
addresses a claim can rest on. A bare task is still refused with
`report_content_refused` and leaves the output area empty — that is the correct
answer, not the gap. **What remains is that the claim's words are the
caller's**: no operation extracts a claim from the material, accepts a model's
proposal, or runs C1, C2 or C3, so the records the product writes stay
`extracted`. **The workbench draws a figure in the same two steps**: its Figure
panel builds the selection from the source the service reports, asks
`POST /approvals`, leaves the question in the Approval panel, and draws with
`POST /analysis` once the answer is granted; a run whose consent is missing is
refused with the service's own reason. `docs/RELEASE-NOTES.md` §2.2 carries
that limit.

**The shard costs are re-measured on the runner, and CI is green.** The three
files this branch added (`test_application_evidence.py`,
`test_event_payload_vocabulary.py`, `test_real_provider_smoke.py`) once had no
measured cost and `tests/test_cli.py` had changed past the partition's slack
since the old `598e788`, so `tests/test_ci_shard_coverage.py` was red on its two
cost checks. That was never fixed by inventing numbers — it was fixed by
`python .github/remeasure_shards.py <run-id>` reading each file's seconds out of
the completed `pull_request` run at `bc043fa`, writing `measured_at` and the
costs, and rebuilding the partition (ubuntu balance 1.389, windows 1.000).
**Head `9799354`: all 17 PR checks pass** — 10 python-quality shards on both
platforms, secret-scan, reference-exclusion, lockfiles, release and web. The
point the earlier paragraph made still holds as method: the membership is a
thing the tree can fix, the numbers are a thing only a runner can produce.

**There is still no model call that leaves the machine.** All four cite-support checks now have bodies, and `IMPLEMENTED_CHECKS` is every one of them — the set no longer distinguishes "implemented" from "not", and what still separates them is that C4 can never return a pass.

**G4's exit test is now demonstrated — and it was not, until this gate's own review made it so.** The end-to-end smoke path (T09) runs from a clean workspace and a temporary database, with no network and no credential, and compares the CLI's `task status --json` against the local API's `GET /task` **field by field** — two hundred and fifty-five fields, none differing — and the report's **bytes by hash**, for each of the four forms, against the file the report operation wrote and the bytes the service serves.

**Three limits are known and recorded.** The API's event stream is **not consumed by the workbench** — the service offers `/events` and `/events/stream`, and the workbench reads neither — and the workbench **cannot switch the selected project**, because the API has no such operation. And the **workbench is never driven against the live service**: its tests use a fake at the `fetch` boundary, so *"CLI and UI show identical Task state"* is discharged **through the API** rather than measured between the two.

**A read still takes SQLite's write lock.** `db/session.py` opens every transaction with `BEGIN IMMEDIATE`, which is right for a write and is ADR-0003 C3's clause; a read is a transaction too, so a read takes the write lock for as long as it is open. The per-request session bounds that window to one request, where before it was the life of the process, and the code's own comment — *"Readers do not block the writer"* — is true of WAL and **not of the application's own reads**. A deferred read connection would be the proper fix, and it was considered and not taken while the gate was closing: it is structural, it re-opens G2's accepted code, and nothing about the gate's exit test needs it.

**The report's reproducible form is Markdown and HTML.** A DOCX is a ZIP whose entries carry timestamps and a PDF carries a creation date, so neither is byte-reproducible by default; the report says so on its own face.

Retrieval now answers the two-negative question (T10): a search that breaks is a `PROVIDER_FAILURE` and never a `no_hit`, and the boundary refuses to hand a caller an empty context. What is still unbuilt around it is the model call the evidence would feed. And the gate is reachable from a ledger rather than from a report: nothing renders a `GateResult` yet, so "a report cites nothing when the gate refuses" is enforced at the gate and asserted at the record model, not observed in a rendered document. That demonstration is still to be made. The ledger's conflict rule covers numeric records about the same cell; the claim-side conflict ADR-0004 A5 also describes is not implemented, because the schema's own uniqueness constraint makes two claim records unable to collide.

## What G5 closed, and what it handed over

**G5 is closed** — LC-P1-13 (evaluation, fault injection, the competitor baseline) and LC-P1-14 (the public alpha handoff: the delivery documents, the release contents, the review dossier, the licence audit), the last two of Phase 1. Its exit test is *"outsider fresh install, 3 fixtures, fault injection, docs and real-provider smoke"*, and **four of the five are delivered and watched**; the fifth, the real-provider smoke, **has never run as a standing witness** and cannot here: no credential is configured in this tree, and Phase 1's **default offline run** reads no environment variable (the provider layer reads one, but only where a workspace's `providers.json` names it). **That is the owner's decision**, and the gate did not make it. **The clause and the class are different things**: LC-P1-03's *"real smoke on at least one provider"* was met once, by hand, at `b237751` on an owner-supplied credential; the protocol's real-model smoke **class** is still NOT RUN and the harness exits 2 because of it. **Two things it handed over are limits rather than defects**: the surfaces never run the recovery pass, so a crash through the CLI leaves an operation `ATTEMPTING` for ever and the next run plans a second one — **the side effect is not duplicated**, so this is a repeated *operation* rather than a repeated *byte*; and the protocol's real-model smoke is still owed. **Owed in a narrower sense since
2026-10-28:** the class has its witness file, it has run against a real endpoint
twice, and the harness will now run it when a reader names it — what is owed is a
**CI secret**, not an implementation.

**The first of those is closed since the gate, and the second still is not.** `run_stage` now calls `labcairn.application.recovery.reconcile_abandoned` after the policy verdict and before any consent is spent: an operation a crash left `ATTEMPTING` becomes `UNCERTAIN`, its stage is blocked with the recovery layer's own reason, and the next `task run` or `POST /stages` is **refused** with `operation_uncertain` instead of planning a twin. **A surface may not answer the doubt itself** — the hash a probe compares against lived inside `args_digest`, a hash of a hash, and no stored row can give it back — so the operator does, with `labcairn task reconcile <operation-id> --expected-sha256 <hash>`; for the inventory stage that number is the one `labcairn sources inspect` prints, and a `CONFLICT` leaves the operation `UNCERTAIN`, the stage blocked, and the probed path untouched. **What remains is the other half**: the transaction the crash interrupted (confirmation, completed stage, receipts) is performed by the run that follows, so one landed effect leaves two operation rows. That is written in [ADR-0003 C2](../adr/ADR-0003-event-and-permission-model.md) and asserted by `tests/test_fault_injection_e2e.py`.

**G4 is closed** — LC-P1-11 (report assembly, export and artefact
versioning) and LC-P1-12 (the Typer CLI and the local FastAPI + React
workbench) — on the independent review at `9381036af0104172f16fe94a6edd2e8cb6d9ae04`, verdict
**PASS WITH NOTES.**
The [gate review](../acceptance/G4-acceptance.md) records
the method, the two mutation tables, the sixty-six findings, and the
limits that are limits. LC-P1-11's and LC-P1-12's own acceptance reviews
are [written up](../acceptance/LC-P1-11-acceptance.md) and
[written up](../acceptance/LC-P1-12-acceptance.md), both **PASS WITH NOTES**.
**The report path's review failed the gate five times**, and the reason is
the same each time: **a property table can be entirely clean and the review
still fail.** The first was on two open defects and five unwatched refusals;
the second on one unwatched refusal the first fix had introduced; the third on
fourteen surviving mutations out of a hundred and sixteen; the fourth —
after the fix that generalised the comparison of the four forms — on **eight**,
in a class the fix's mechanism could not reach: **what a form says about
itself outside its own text** (the DOCX's title property, the PDF's title and
author, and the list-item shape of the Markdown and the DOCX); and the fifth,
at `86e0226`, on **four** — which the fix under review had closed down to, and
which **found a real defect of its own**: the list-item witness comparing a
count rather than a marker.

**The three surfaces' review came back BLOCKED**, on two blockers and six
notes, one of the blockers sitting directly under the gate's own exit test —
**and its re-verification came back BLOCKED again**, on two mutations that
survive: **the witnesses for one of the blockers had been deleted by this
gate's own composition**, and the demonstration's own comparison of the two
surfaces is unwatched. **Every finding is fixed**, and both reviewers re-ran
their own mutations against the fixed code.

**G5 is the public alpha, and it is closed.** LC-P1-13 (evaluation, fault
injection and a competitor baseline) and LC-P1-14 (the handoff dossier, the
licence audit, and the two READMEs), delivered at `72154cd` (PR #116) and
`3852cde` (PR #117), closed at `ff9afc5` (PR #118) on **two independent reviews**
that wrote none of its fixes — the first's verdict moved **FAIL → PASS** after its
findings were fixed, the second is **PASS WITH NOTES**. Its ten subtasks (T00–T03,
T05–T09) are merged; **T04 is the owner's** — the real-provider smoke needs a
credential and an authorisation. **Its half moved on 2026-10-28:** the class now
has the witness file `manifest.REAL_MODEL_SMOKE_FILE` had named since T04 without
ever having one — `tests/test_real_provider_smoke.py` — and it **ran twice** on a
credential the owner supplied for the purpose (`MiniMax-M3.1-Flash`, protocol
`anthropic`, endpoint `https://api.minimax.cn/anthropic`: `tool_calls` and
`usage_reporting` ok, both structured-output forms declined inside pydantic-ai
before a request was sent, which is §2.14's claim re-measured). **What is still the owner's is narrower now, and it is a ruling rather than a
setup:** the credential is configured on the repository and
`.github/workflows/provider-smoke.yml` spends it — on a schedule and on demand,
and **deliberately not as a required status check**, because a check that can
only pass where a secret exists is one branch protection would wait on forever.
**The workflow has run on GitHub**: dispatch 40663728369 at `0adfbe3`, 2026-10-28
09:22 UTC, green, printing the same endpoint fingerprint the two local runs did.
Getting the file to parse at all was its own finding — `${{ runner.temp }}` is not
in the job-level `env` context, and GitHub answers such a file with `HTTP 422` at
dispatch, which looks from inside the repository exactly like a workflow nobody
ever dispatched. So the default harness run still reports the class NOT RUN and
exits 2, and the question left was whether a scheduled, non-required witness is
what §1.4.2 meant. **Ruled 2026-10-28: yes.** The owner accepts
`provider-smoke.yml` (scheduled + dispatched, non-required) as this gate class's
discharge, because a required check that can only pass where a secret exists is a
check branch protection would wait on forever. The default harness's NOT RUN
stays on the record as what the offline path actually reports — a fact, not a
claim of a passing run.
The [gate review](../acceptance/G5-acceptance.md)
carries the method and every finding.

**§1.4.1b is ruled too, and the harness has the answer rather than a note
beside it** (2026-10-29). A skip whose reason names **a fact of the machine** —
an OS, a filesystem, a volume with no 8.3 short names — does not fail a blocker,
because the CI matrix runs both platforms and no single runner carries the pair;
**any other skip fails it**, by name and with the reason recorded, for a
blocker's own witness cases and for the sixth blocker's required CI tests alike.
The accepted ones are **named in the row** — a witness case by its node id and
pytest's own reason, a required CI test by its file under the category it fell
in. The owner was asked whether the ruling covers witness cases and not
only the sixth blocker's required tests, and chose **all blockers** — which is
what the second blocker's FAILED row needed.

**The G1/G2 human review is prepared, not done.**
[`acceptance/G1-G2-human-review-checklist.md`](../acceptance/G1-G2-human-review-checklist.md)
is the document a named human works from: every clause of both gates with the
node id that holds it, the mutation that must go red for each one, the three exit
demonstrations with their check counts re-counted from the source (36 / 14 / 18),
the commits each gate has taken since it closed, and the four places where these
two records are weakest — most of all that **four of G1's thirteen clause rows
and all six of LC-P1-07's were recorded by behaviour rather than by node id**, which is why
the checklist re-derives them, and why a witness now resolves each cited id
against the class the citation names — three of the first hand-derived ids were
wrong in ways reading cannot detect. The ruling that the retro-reviews are *procedural independence,
not human* stands until that review is executed and written back.

**The licence audit's factual half is done**
(`acceptance/LC-P1-14-font-licence-audit.md`): no third-party font file
reaches any artefact, so the GPL font reportlab bundles does not attach to
what a user receives. **What is left is the owner's** — the copyright and
the root licence, which `LICENSE.PENDING.md` grants no rights over today, and
which blocks any open-source claim until it is replaced by an actual
licence.

**And the piece of work G5 found by accident is landed.** G1's exit
demonstration had been broken since G1 closed, because nothing ran it, and the
reason was a defect in the product's path layer: on Windows a write to a new
file under an 8.3 short-spelled directory was refused. **It is fixed** —
`src/labcairn/security/paths.py` counts a short name as one part, with
`test_a_new_file_under_a_short_spelled_root_is_not_refused` and
`test_a_path_outside_a_short_spelled_root_is_still_refused` as its witnesses —
**and the skip that had been waiting for it is gone**, so G1's demonstration is
watched on every platform (`tests/test_earlier_exit_demos.py`). **That skip was
itself the finding**: it outlived the defect, and the harness counts a skipped
witness as a failed blocker, so the protocol's first blocker was held down by a
reason that had already been fixed (the gate's own review records it as S6/R3,
found independently by both parties). **§1.4.1b's ruling keeps that case
failing**: the categories turn on what the skip's own reason says, and a reason
that names an open product defect names no fact of the machine —
`test_a_witness_skip_outside_the_accepted_categories_still_fails` is the witness
that such a skip still holds its blocker down. The two are classified apart on
purpose: a defect-skip is one the suite must not settle for.

## How G4 went

LC-P1-08 (material parsing and locators) → LC-P1-09 (FTS5 retrieval and the evidence ledger) → LC-P1-10 (bounded statistics and deterministic plots).

**LC-P1-08 was accepted with notes by owner decision, not by independent review.** Its acceptance review is [written up](../acceptance/LC-P1-08-acceptance.md) and records eight defects found and fixed — most seriously, a two-column PDF storing sentences the author never wrote and marking them citable. The review and the fixes were the same party, so the board's rule was not discharged; the owner decided on 2026-10-18 to proceed without it, and the board records that as a decision rather than as a review. **It is discharged now**, by the independent review at `d114810` — the [gate review](../acceptance/G3-acceptance.md) records the method and the mutation table, and the three findings it added, all fixed in `f0f7563` (PR #70).

**LC-P1-09 is implemented and reviewed — PASS WITH NOTES.** All ten subtasks are merged, the acceptance review is [written up](../acceptance/LC-P1-09-acceptance.md), and it found three defects, all of the family LC-P1-08's review found eight of: a claim made in a docstring that the code did not enforce, and a column nothing ever wrote. Two are fixed; the third is a **clause of the acceptance that is not discharged** — the *fabricated DOI* half has no implementation, and the gap is structural rather than an oversight. The review and the fixes were the same party, so the board's independent-review rule was **not discharged**; the same caveat as LC-P1-08. **Both are discharged now**, by the same independent review at `d114810`.

One thing worth knowing before reading the code: **`SourceIndex`'s members were never specified by ADR-0004.** The ADR requires C1 to "fail if an anchor id is unknown", but the Protocol it names takes no id — `locate` wants a whole anchor and `content_hash` a source id, and a record carries only `anchor_ids` as bare strings. Revision 0007 and `load_anchor` close that seam. It is recorded as an execution note at the head of ADR-0004, because it is the requirement's missing implementation rather than a change to the contract.

**G3 is closed, on an independent review at `d114810`** — the board's rule that a row is marked done only when an **independent** review at a named commit says so is satisfied for all three of the gate's work orders. A reviewer that wrote none of the fixes worked through all fourteen fixes by breaking each one, implementation only and never the test, and **no mutation survived**; the verdict is **PASS WITH NOTES**. The [gate review](../acceptance/G3-acceptance.md) records the mutation table, the three things the gate asked an independent reviewer to look at — LC-P1-08's two-column threshold, LC-P1-10's manifest not naming a version for the renderer, and the fact that **G1's and G2's exit demonstrations are run by nothing** — and the three findings the review added. All three findings are fixed in `f0f7563` (PR #70).

**LC-P1-10 is [reviewed and accepted](../acceptance/LC-P1-10-acceptance.md) — PASS WITH NOTES.** [Task breakdown](../plans/LC-P1-10-task-breakdown.md): eleven subtasks (T00–T10) with a file-ownership map, and the work order's five acceptance clauses plus the ADR-0004 conditions it touches each mapped to the subtask and test that carries them.

**T00 — the dependency decision — is [ADR-0012](../adr/ADR-0012-chart-rendering-library.md).** `matplotlib>=3.9,<4`, locked at 3.11.2, seven new packages and 78.7 MB of installed bytes. Two things in it are worth knowing before the renderer is written:

- **The licence was read from the distribution's own `LICENSE` file, and it brings a second obligation.** matplotlib's own licence is PSF-style and permissive — but the wheel **bundles forty TrueType fonts under two further licences** (DejaVu: Bitstream Vera; STIX: SIL OFL 1.1), so the G5 licence audit must cover the bundled fonts and not the root licence line alone. That is exactly the failure ADR-0004 records for paper-qa.
- **The determinism controls were measured, and the one you would guess is not the one that works.** Fixing `svg.hashsalt` **alone is not enough**: matplotlib writes a creation date into the SVG metadata, and two renders a second apart get different ones. The two controls govern different things — the **date** governs stability *within* a process, the **salt** governs it *across* processes, because left unset matplotlib generates a fresh random salt per interpreter. PNG needs neither. `tests/test_analysis_dependency.py` fails if either control is removed, and its cross-process assertion is the only one that can observe the salt at all.

**T02 and T03 — the operator contract and the selection.** T02 fixes the id grammar (`labcairn.analysis.<name>`) and the one reference spelling (`…@1.0.0`) a manifest quotes; the catalogue of shipped operators lands with the operators themselves, because it has to be built from their own id constants, exactly as `evidence/catalog.py` is built from the checks' constants. T03 is the selection — which columns, which rows, and a **declared** missing-value policy — and it **moved the quantity reader to `labcairn/sources/quantity.py`**, so the ledger and the analysis layer cannot answer "is this a number" two different ways. C3's existing tests pass **unmodified**, which is the proof the move changed no behaviour.

**T01 — the fixture corpus — is the first thing in the repository that is a CSV or a spreadsheet at all.** Eight committed CSVs under `tests/fixtures/analysis/`, each with a hand-written `<fixture>.expected.json` beside it, and a test that recomputes those values with Python's `statistics` — an implementation that is **not** LabCairn's, so an expectation cannot share a bug with the code the operators will be written against. The corpus is also where the format asymmetry was pinned in data rather than in prose: `holes.csv` and `holes.xlsx` are the same table with one value cell emptied, and the CSV **keeps** the cell (empty) while the spreadsheet has **no cell at all** — so a spreadsheet's rectangular extent is not recoverable from the ledger. A second difference is in the same pair: a spreadsheet's header row *is* a set of addressable cells (A1, B1) and a CSV's is not.

**T04 — the descriptive operators and the catalogue that holds them.** Seven operators (`count`, `sum`, `min`, `max`, `mean`, `median`, `stdev`) and the catalogue built from their **own id constants**, for the same reason `evidence/catalog.py` is: **one id has one spelling**, and the manifest quotes an operator by name, so two spellings of one operator would be two manifests that do not compare equal. A catalogue cannot precede its implementations, so it landed *with* the operators rather than before them — LC-P1-09's precedent, where the evidence catalogue was created in T08, after the checks it registers existed. The unit rule is C3's, inherited: compared as written, never converted, and the known false negative (`kilograms` and `kg` are one unit spelled two ways, and a selection holding both is refused, naming both tokens) is stated rather than hidden.

**T05 — the grouped aggregate.** One vetted statistic per group, over a selection, returning a **table** rather than a number: there is no "the grouped mean" of three groups, and a number would have thrown away the very thing that makes it grouped. The statistic is **composed** from a registered operator rather than reimplemented, so the grouped mean and the scalar mean cannot drift apart — there is exactly one implementation of "mean" in this codebase — and an aggregate that names no registered operator is a **refusal**, not a guess. The aggregate's unit is checked **per group** and not across the selection. A group with no quantity has **no statistic** (never zero), and its reason names **that group** rather than the selection, because in a table of groups "the selection" is the wrong thing to blame. The group key is the cell's text **as written**, so the empty key is a group while a cell that was never recorded is not — for a spreadsheet those are the same observation, and inventing a key would be inventing a group.

**T06 — the chart recipe.** A figure's editable source is a JSON document of exactly **three** parts (data, encoding, output), with **no script beside it and no way to run one**. That is what makes the work order's *"Explicitly no general-purpose model-authored code execution"* **satisfiable rather than aspirational**: a recipe names an operator from the catalogue, a selection, an encoding and an output, and the renderer draws it. The figure's numbers are therefore a **vetted operator's output** and not a second reading of the file, and the parameters are checked by **the operator's own argument model**, so the question "which parameters does this operator accept?" has exactly one answer and it is the operator's. The **caption and the interpretation are separate fields**: ADR-0004 A10 holds that an interpretation is never machine-verified, so the marker that says so belongs to the **renderer** and cannot be left out by forgetting.

**The acceptance review's verdict is PASS WITH NOTES**, and its three findings were closed before the verdict rather than after it: a unit check that passed **vacuously** (the function that reads a column header's declared unit had no caller in the production code, so a table that keeps its units in the header found nothing to check); four properties no test observed; and a caption drawn **across the axis tick labels**, found by the exit demonstration. Two limits are recorded rather than closed — the manifest names **no version for the renderer**, and the aggregate's numbers are not re-checked by C1, C2 or C3 — and the review was **not independent**, which was the same open item LC-P1-09's review carried. Both are discharged now: the independent review at `d114810` found the manifest limit to be a deliberate, stated one rather than a defect, and closed every one of the gate's fourteen fixes under mutation.

**T10 — the exit demonstration.** `examples/analysis_demo.py`, in the shape of `examples/g2_exit_demo.py`: a controlled CSV is ingested, a grouped aggregate runs and prints the value **and the cells it came from** (each with its locator), a figure is drawn from the recipe, the manifest prints its six fields and both hashes, the figure is rendered twice and the bytes compared, and then the **input file is changed**. The last step uses the repository's own machinery rather than a comparison the demo wrote: the material's checkpoint no longer verifies, `invalidate_on_source_change` marks the figure and the manifest `STALE` with the reason, a run over the new bytes is refused, and the figure on disk is unchanged. The **recipe is committed** and the run's arguments are read out of it, so the recipe and the run cannot disagree. And unlike the earlier exit demonstrations, this one is run by a test — `g1_exit_demo.py` and `g2_exit_demo.py` are run by nothing, and a demonstration nobody runs is one that quietly stops working.

**T07 — the deterministic renderer.** A figure is drawn from the **recipe** and from **the operator's result object**, so the numbers plotted are the operator's numbers, and the renderer neither re-reads the file nor re-implements the aggregate. The chart operator that does the drawing is a **catalogue entry** (`labcairn.analysis.chart@1.0.0`), so *"a vetted chart operator renders"* is code rather than convention, and the renderer dispatches through the catalogue to it. `render()` returning `None` means exactly one thing — *this result does not produce a figure* — and everything else is a **refusal** that names the fault. The determinism controls were **demonstrated rather than asserted**: the SVG's creation date and its salt each shown to matter, **PNG shown to need neither**, and a hostile ambient `matplotlibrc` shown unable to change the bytes; the `rcParams` come from a **declared, hashed** defaults file, and the renderer's declared drawing parameters (the figure's size, the histogram's bin count, the settings' digest) are published as constants the manifest's environment does **not** carry — recorded in the breakdown's §5 as something this work order does not deliver.

**T08 — the reproducibility manifest.** A computed number is a statement about a **derivation**, and what makes it checkable is not a check but the document: the input file's hash, the selection, the operator and its version, the parameters, the recipe and the output's hash — the **six fields** the work order names. The manifest is the document; the receipt is the record that points at it, and the `artifacts` table already mirrors the receipt field for field, so there is **no new table and no migration**. And **one hash lineage**: the manifest's input hash, the selection's `content_sha256`, the source's `content_sha256` and the file's actual bytes are the same value, and the builder refuses to produce a manifest in which they are not — the definition of that value already had two implementations in this repository, and the manifest reuses one of them rather than adding a third.

**T09 — the run path.** From a granted `analysis.run` to a recorded artefact: admit the path into the named source root, build the selection, resolve the source (the ledger's row, the file's bytes, the source's readability), evaluate the operator, `prepare()` the environment, write the manifest, render, and record the receipts. **The consent is the existing machinery and is not optional** — the digest is *recomputed* at the moment of use over the capability's canonical arguments, so an approval to analyse one selection does not authorise another, and the approval's source binding is re-hashed, so a file that has drifted since is a refusal rather than a run over different bytes. Every refusal is one type with a machine-readable reason and a message that names what is wrong, and the refusals the machinery underneath raises are translated rather than swallowed, with the original kept as the cause. A refusal **before** the consent point does not spend the approval — re-asking a human is cheap — and the operator's refusal does, because the operator's evaluation *is* the operation the capability names. The bounds are the enforceable ones: a row limit and a cell-count limit, both checked **before** a cell is read, because a limit checked afterwards is a report and not a bound. The one that cannot be enforced — a wall-clock timeout on an in-process numeric loop — is named in `UNENFORCED_LIMITS` rather than shipped, because a timeout that does not fire is worse than no timeout at all.

Three facts about the rest of it are worth having before the code is written, because each one removes work rather than adding it:

- **No schema migration is needed.** `ArtifactReceipt` already reserves `ArtifactKind.FIGURE` (*"LC-P1-10's concern"*), `ArtifactKind.MANIFEST` and `ArtifactProducerKind.ANALYSIS_OPERATOR`, the `artifacts` table already mirrors the receipt, and `ComputationLocator` was written for this work order — its docstring names ADR-0004's re-evaluation trigger 3 as the reason it exists.
- **The repository contains no CSV and no XLSX file at all.** `tests/fixtures/` holds `papers/` and `retrieval/`, and a repository-wide search for `*.csv` and `*.xlsx` returns nothing. So the "controlled fixtures" the acceptance clause names are a **deliverable of LC-P1-10**, not an input to it — the same gap LC-P1-09's review recorded when it noted that every C3 case was a row written by a test.
- **An aggregate cannot be an evidence record, and the schema already says so.** `evidence_records.anchor_ids` name rows in `source_anchors`, whose `locator_key` is CHECK-constrained to the four extractable kinds, and `render_locator_key` raises for `LocatorKind.COMPUTATION` because a derived number has no address in `source_texts`. The owner chose to keep it that way on 2026-10-19: an aggregate is an **artifact** with a manifest, and the ledger keeps doing what it is good at — statements about located cells. The cost is stated in the breakdown rather than glossed: **a figure's numbers are traceable to the input file but are not re-checked by C1, C2 or C3.**
- **The two spreadsheet formats disagree about what an empty cell is, and it was measured rather than assumed.** A **CSV** emits a `source_texts` row for an empty cell, so empty cells can be counted; an **XLSX** emits no row for one, so a spreadsheet's **blank cells are not recoverable from the ledger** — a cell that holds nothing and a cell that was never there are the same observation. The consequence is narrower than "the missing count is unknown": the count of *addresses with no recorded value* is known in both formats; what is not knowable for a spreadsheet is **how many of them were blanks the author left**, and a range that overshoots the table cannot be told apart from a range full of blanks. A count of zero is never used to mean "unknown" — ADR-0004 A8, applied to statistics.


**Its PDF library question is settled.** [ADR-0008](../adr/ADR-0008-pdf-ingestion-library.md) puts it on pdfplumber + pdfminer.six, both MIT, rather than PyMuPDF, whose AGPL branch would have constrained LabCairn's own MIT release. Nothing needed undoing.

**The two-column PDF question is also settled, as a refusal.** Reading order is not reconstructed. A page that reads as two columns is refused and disclosed rather than extracted, because splicing two columns stores sentences the author never wrote — that defect was real, reproduced, and is the reason the refusal exists. Rotated text is still not detected, and there is no two-column paper in the repository to test detection against. The refusal has a **band below it** — a two-column page whose rival column holds under 30% of the page's line starts is not refused — and that band is stated in ADR-0008 and in the adapter's own docstring rather than left to be discovered from a wrong citation.

**G4's plan is written, and the gate closed on it.** [LC-P1-11 and LC-P1-12's task breakdown](../plans/LC-P1-11-12-task-breakdown.md): the report's document model with four renderers over it, the report artefact manifest, the revisions and the staleness, the content checks, and then the three surfaces — the Typer CLI, the local FastAPI service and the React workbench — behind one application layer they all call. **The five decisions in §1.4 were taken by the owner on 2026-10-20**: a report cites **locators only** (the source model has a place for identifiers that ingestion never fills and that nothing resolves); the CLI and the API serve the **same bytes**, so the gate's exit test is a hash comparison; the report's **reproducible form is Markdown and HTML** (a DOCX is a ZIP and a PDF carries a creation date, so by default neither is); the local API **refuses a foreign origin** and requires a token minted at start-up; and a receipt's chain is a **flat ancestor closure**, because the staleness walk that already exists is one hop, so the material's hash has to be directly in the report's chain. **The spine of G4 is in `main`, and so are the three surfaces' code**: the report's document model (`a9e7cf6`), the report artefact manifest (`6dcf2f1`), the four renderers (`d73f433`), the content checks (`3956df7`), the revisions (`a7697e7`), the document builder (`a84a10b`) and the layer's report operation (`2e485b0`) are merged, and so are the one application layer the three surfaces call (`d114810`, which brought the store's nine missing list and read queries with it), the Typer CLI (`99c3d49`), the local FastAPI service (`60ebe11`), the layer's event read (`e344a93`), the source id's type (`ba07dd5`) and the React workbench (`6c92e41`). The end-to-end smoke path (T09) is merged, and **G4's exit test is demonstrated**: the CLI's task document and the local API's, field by field, and the report's bytes by hash. G3 is closed, on the independent review at `d114810`, and G4 is closed, on the independent review at `9381036af0104172f16fe94a6edd2e8cb6d9ae04` — verdict **PASS WITH NOTES**.

## Carried limitations, none blocking

- **LC-P1-08:** rotated PDF text is **not detected**. A rotated page would
  extract in the wrong order and nothing would record it. ADR-0008 constraint 7
  is unmet, and this is the honest reason the two-column work stopped at
  refusal rather than proceeding to reconstruction.
- **LC-P1-08:** the two-column detector is bracketed against single-column
  fixtures, not calibrated against two-column ones — there is no two-column
  paper in the repository to calibrate against, and the two-column CC-licensed
  material that would calibrate the other direction could not be obtained
  (ADR-0008 records the search). The independent review of G3 found the
  **coverage band** below the threshold unstated: a two-column page whose rival
  column holds under 30% of the page's line starts is stored `readable` and
  citable, with its columns spliced. The threshold is 30% — the lowest share
  that refuses nothing in the real corpus, whose own single-column pages
  cluster at 20–26% — and the band **cannot be closed with this signal**,
  because those real single-column pages sit in the same place. The residual
  is stated in ADR-0008 and in the adapter's docstring and pinned by a test of
  its own.
- **LC-P1-08, discharged by LC-P1-09 and by LC-P1-11:** anchors were validated only in their
  **positive** direction — no code consumed a locator and returned content, so
  nothing showed that a wrong locator misses. `locate_anchor` now does exactly
  that, and C1's tests assert both halves: a locator naming page 99 of a
  three-page paper fails, and the failure names that address and no other.
  The end-to-end version came with LC-P1-11: the report's link check resolves
  every citation against the material and acts on the answer, so an address
  that does not resolve is **refused** and the report cites **nothing** in its
  place — not the nearest page and not the last page.
- **LC-P1-08:** `UNPARSEABLE` is a mixed bucket — a container that would not
  open, and a page deliberately not read. Both are honestly "not citable, here
  is why", but only the disclosure separates them.
- **G1:** ~~`ApprovalLedger.consume()` does not resolve the capability against the registry. Only `policy.evaluate()` turns an unknown id into DENY, and nothing enforces that a caller evaluates first.~~ **Closed**: `consume()` now asks the registry and refuses with `capability_unregistered` (`src/labcairn/security/approval.py:215-222`); `tests/test_security_approval.py` and `tests/test_recovery_approvals.py` are the witnesses.
- **G1:** path-guard tests ran on Windows only. POSIX ADS and case semantics are unverified.
- **G1:** ADR-0006's outbound-consent bridge is not built. Both modules exist.
- **G1:** structured-output capability is unmeasured — both probes fail in pydantic-ai's client layer before a request is sent.
- **G2:** `ArtifactLedger` is in memory. LC-P1-07's ledger does not survive a restart; the store does.
- **Cross-gate:** the Gitleaks allowlist guard is textual and has a multi-line/nested TOML weakness.
- **Cross-gate:** the README capability-claim detector has known holes. It is a floor, not a truth-checker.
- **Cross-gate:** copyright ownership is unresolved and there is still **no `LICENSE` file**. The project describes itself as in development with open-source licensing pending.

## Merge authority

The implementing agent merges its own PRs after both the parent and a non-implementing reviewer have signed off and all required CI checks pass. Merge authorisation comes from the project plan, not from an external auditor.

## Escalate to the project lead

Expanding data access scope, write permission to original material, unapproved outbound transmission, any model-generated code execution, and major architecture change. The PyMuPDF licence obligation is now **resolved** (ADR-0008) and no longer needs escalating; **copyright ownership remains unresolved** and still does.
