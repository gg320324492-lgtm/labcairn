# Phase 3 planning decisions — 2026-11-06

**Status:** owner decision record. This is a record of what was decided on
2026-11-06 for the Phase 3 planning material. It is not a work order, a
status board, an ADR, an implementation instruction, or evidence that Phase 3
has started.

**Baseline:** `b3fba5f1581b066e64c2bc7b884ebc952605245d`, printed by
`git rev-parse HEAD` at the start of this work. No other commit SHA is
quoted in this record.

## 1. Starting material

Owner-supplied Word and PDF files named `LabCairn Product Definition and
Phase 3 Plan` were supplied as external product-design material. Two Chinese
working drafts were found untracked in the checkout:
`docs/plans/PHASE_3-execution-plan.md` and
`docs/plans/PHASE_3-design-traceability.md`. They had not been committed,
pushed, opened as a pull request, or measured by CI. Byte-for-byte copies of
those Chinese drafts and the Word extraction are kept outside the repository
under `E:\labcairn-local\phase3-plan-review\`.

The earlier claim that a "complete execution plan" had been delivered is not
borne out by the repository state: the drafts were untracked. This record
does not treat an untracked draft as a delivered plan.

## 2. Owner decisions

The owner was asked to decide the depth of the planning work. The recorded
answers were:

1. `English planning proposal` — convert the Chinese working drafts into an
   English proposed draft, synchronise current pointers, and still write no
   Phase 3 product code and dispatch no implementation work orders. Gate,
   ADR and board planning come first.
2. `Windows internal trial exit gate` — accept the Word brief's proposed
   Phase 3 exit gate as a Windows research-group internal trial. Multi-platform
   public distribution moves to a later work package, and the ROADMAP is
   updated in the same delivery.
3. `Preserve source gaps honestly` — mark Q76, Q81 and Q86 as
   `RECOMMENDED_ONLY`; Q77, Q82 and Q87 as `ORIGINAL_MISSING`; and Q96 as
   `CONFIRMATION_MISSING`. Do not fill a missing question or turn a
   recommendation into a confirmation.
4. `One delivery PR and one runner run` — authorise a single delivery PR and
   a single CI run for this planning material. No provider credential, real
   model request, package signing, tag, release, or direct push to `main` is
   authorised by that answer.

The owner also instructed this session to take over the planning material,
repair gaps against the repository's actual state and the execution brief's
direction, and ask only where a decision is genuinely theirs. The repair is
recorded as an English code-facing gap register; it is not product code.

## 3. What these decisions change

- The proposed P3 direction changes from the ROADMAP's earlier
  `multi-platform public release` row to a Windows internal-trial exit gate.
  The ROADMAP, CURRENT, CHANGELOG, documentation index and scoping pack are
  revised together so the plan and its records do not drift.
- The two Chinese drafts are replaced by English `Proposal — not approved`
  documents. Chinese source text, the Word/PDF files and the extracted
  `source.md` stay outside the public repository.
- A dated code-facing gap register names the real product entry points and
  the measured gaps. It does not change `src/`, `tests/`, `migrations/`,
  `web/` or `.github/workflows/`.
- The earlier `PHASE_3-scoping-pack.md` remains the record of the first
  scoping authorisation. This decision record supersedes only its
  "no candidate scope family is opened in the next round" line: the owner has
  now chosen a proposed exit gate. It does **not** open a board.

## 4. What remains an owner decision

The following are explicitly not decided by this record:

- formal Phase 3 board, ticket numbering, gate names and gate split;
- reviewer form, including whether an independent agent session may stand in
  for a human reader in a Phase 3 gate;
- provider, model, permitted outbound scope, budget, credential holder and
  stop-loss for the bounded real-model validation;
- Electron or any other desktop shell selection and implementation;
- third-party plugin/MCP execution;
- signing, notarisation, store accounts, release tag and public release;
- any real advisor or student trial participation, which cannot be simulated
  by an agent and reported as human use;
- the seven unresolved source questions listed in section 2;
- the 35 unaccepted Phase 2 model-proposal edges, Phase 2's
  `real_model_smoke = NOT RUN`, and the archived ADR-0020 / LC-P2-28.

Phase 2's measured exit gate and administrative closeout are unchanged.
Phase 3 implementation has not started.

## 5. Delivery discipline

One delivery branch, one pull request and one runner run are authorised for
this planning material. `main` is protected; no direct push is attempted.
A new test file, if any later work creates one, must declare `pytestmark`,
appear in exactly one `.github/ci-shards.json` shard, and be registered in
`tests/evaluation/manifest.py`; shard costs must be re-measured from a runner
log, not from a local clock. No runner result is claimed before the pull
request reports one.

## 6. What this record does not do

It does not implement product code, open a work order, accept a design-only
ADR, accept a model edge, configure a secret, spend money, sign a package,
publish a release, enable auto-merge, or claim a Phase 3 gate result.
