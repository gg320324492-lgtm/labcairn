# LC-P3-06 — one-model bounded validation: substitute-first half

**Date:** 2026-11-10.
**Branch:** `claude/nice-merkle-5b4007` (worktree
`E:\LabCairn\.claude\worktrees\nice-merkle-5b4007`).
**Base:** `4855ea66d71ea8363aa578e7ca6b00e03efde7de`.
**Code head:** `06d8c7544aeb7daaf12bce704fbf1053418f3d0b` (two commits:
`0b4cf89` product modules, `06d8c75` witnesses and registration).
**Final head of this work:** `899da8368a66449dcdfe301759c6ef2a9f804e2d`,
the record commit; the follow-up correction changes only this heading
block. The full SHA of any later head is printed by `git rev-parse HEAD`
in the checkout.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. The board row stays the commander's to move; this record claims no
`PASS` for Phase 3 G3 or for the "One real model" acceptance row.

**Authorisation:** `docs/plans/PHASE_3-work-orders.md` §11 §4.9 (the seven
answers, 2026-11-09) and §4.8's **left column only**. Q1+Q2 name
`MiniMax-M3.1-Flash` / `anthropic` as the real route; Q3 per-excerpt
digest-bound outbound scope; Q4 20 requests / 50 000 tokens; Q5
`credential_file` on the trial machine, `providers.json` names the path and
never the secret, and the `provider-smoke` GitHub secret stays uncreated; Q6
synthetic samples first; Q7 compound stop-loss watched by the operator. The
dev build runs before `LC-P3-05`'s installed build.

**Zero outbound, literally.** Every call in this work landed on
`FakeEndpoint` from `tests/provider_fakes.py`: no socket, no credential read,
no supplier route, no spend, no real model. Phase 2's
`real_model_smoke = NOT RUN` and its 35 unaccepted model-proposal edges keep
their own records verbatim (§4.3). CI stays on substitutes. Nothing under
`providers.json` was created or read.

## 1. What landed

| Area | What it is |
|---|---|
| `src/labcairn/providers/deidentify.py` | The de-identification pipeline (`DeidentificationPipeline`, `DeidentifiedCase`), the execution plan's three `SampleClass` values, and the `SampleFingerprint` record format. |
| `src/labcairn/providers/bounded_run.py` | The bounded run harness (`BoundedRun`, `CompoundStopLoss`, `RunRecord`), Q7's two-arm stop-loss, Q3's per-excerpt digest-bound consent check, and the digests-and-counts run record. |
| `tests/test_provider_deidentification.py` | 13 witnesses (unit) for the pipeline, its refusals, the CJK ceiling outbound, and the sample/fingerprint format. |
| `tests/test_provider_bounded_rehearsal.py` | 20 witnesses (integration) for the four-rung ladder, the three degraded paths, the stop-loss, and the record. |
| `tests/evaluation/manifest.py`, `.github/ci-shards.json` | Two new test files registered in three places: `pytestmark` (`unit` / `integration`), one manifest row each (`provider-redaction` / `approvals`), one shard per platform, `0.0` local cost placeholders. |

No file outside these areas was touched. `src/labcairn/application/`,
`src/labcairn/papers/`, `src/labcairn/api/`, `web/`, the CI workflow files and
`providers.json` were untouched. `providers/` still imports nothing from
`labcairn.security` (`tests/test_capability_namespaces.py` watched this).

## 2. The de-identification pipeline and the order it fixes

The work order says *redaction runs BEFORE the outbound payload is built*.
That is a structural claim here, not a comment: `DeidentifiedCase` — the only
shape `BoundedRun.submit_case` accepts — has exactly one construction path,
`DeidentificationPipeline.redact_case`, and that method verifies before it
mints. Checks, in order:

1. **Run-length**: no `GRAM_WINDOW` (8) consecutive whitespace-separated
   words of the material *or of any excerpt the caller named* survives in any
   rendering. The corpus is material plus excerpts because a caption or a
   table row can carry a run the material text does not.
2. **CJK ceiling outbound**: no Han run of `HAN_RUN_CEILING` (8) characters
   survives in any rendering. The repository's own CJK pin watches tracked
   files; this one watches outbound text. The escape-built regex and the
   escape-built test payload leave no Han run in the tracked files — the
   measured table stayed at 49 files with no new entry.
3. **Named secrets**: a secret the caller knows by name (a credential, a
   subject name) must not survive verbatim; a failure refuses the whole case.
4. **Final scrub**: the renderings pass through the existing
   `providers.redaction.Redactor`, removing credential-shaped text even when
   the n-gram check cannot see it.

The pipeline **does not rewrite text**. Deciding what a name, an affiliation
or a strain designation is belongs to a person; the product decides only
whether the replacement worked. A refusal's message names the check, the
field and the run length — never the surviving text, so a refusal cannot be
the leak's own log line (`test_a_refusal_echoes_no_material`). Each minted
case carries one `prompt_digest` per *rendered* excerpt, the adapter's own
domain-separated spelling, so the approval binds what leaves and the
`ExchangeRecord` computes the same number from what it saw.

## 3. The refusal ladder, rehearsed end to end

The harness wires the real `PydanticAiModelProvider` itself — budget,
probe record, ledger, usage capture, timeout and runner are the run's own —
and builds one adapter per request with that request's
`OutboundConsent` port. The application side (the test) assembles real
asked/granted approvals through `request_approval` / `grant_approval` and
real `OutboundApproval` ports; `DigestBoundPort` adds the digest the
approval binds. The substitute is the recording upstream, so "no outbound
call" is `endpoint.calls == []`, never a raised exception plus a hope.

| Rung | The rehearsal | Zero calls? | Mutation that reddens its witness |
|---|---|---|---|
| **Budget preflight, fail-closed** | `BoundedRun` refuses a budget naming no ceiling ("no number → no call"); a token ceiling with no probe record is `BUDGET_ENFORCEMENT_UNAVAILABLE`; Q4's 20 / 50 000 is the run's fixture; a spent `max_model_requests` refuses before the request is built. | Yes (4 witnesses) | `_budget_names_a_ceiling` forced true (M4); the adapter's `self._budget.require(..., pending_requests=1)` removed (R1). |
| **Probe-record gate** | With `ProviderCapabilities.unverified(...)`, the capability rung refuses: *a supplier name is not a capability*. With a probed record, the same fully authorised case is sent exactly once per field (2 calls: prompt + one excerpt) — the positive control. | Yes | `adapter._gate_capabilities` short-circuited to `return` (R2). |
| **Consent bridge** | `MODEL_REQUEST` is the only `Effect.NETWORK` capability and `default_policy()` says ASK for it; a pending approval refuses with `OUTBOUND_REFUSED`; an excerpt whose port is bound to a **different digest** is refused for the whole case before its first request is built; one port for several requests is refused; the port's own `OutboundRefusedError` is driven directly through the adapter. | Yes | `adapter.send`'s `self._consent.require(request)` removed (R3); `bound_excerpt_digest != bound` disabled (M5); the whole-case precheck removed (Q3 rung mutation). |
| **Capability refusal** | A probe record with `TOOL_CALLS = UNSUPPORTED` and a run requiring `TOOL_CALLS` refuses before the wire. | Yes | `capabilities.require_all(self._required)` removed (R4). |

Each of the four rungs was mutated **at its product source** and the named
witness turned red (R1–R4), with the two harness-side rungs (M4, M5 and the
whole-case precheck) measured separately. The digest-binding precheck was
added because the first rehearsal found a real defect: checking per-request
inside the loop would let request 0 leave before a mis-bound excerpt was
refused. A half-sent case is not de-identification.

## 4. Degraded paths and Q7's compound stop-loss

Measured with the substitute, per §4.6's own wording: *"Budget or permission
failures cause no outbound call; timeout and unavailability have explicit
degraded paths."*

| Path | Measured behaviour |
|---|---|
| Budget refusal | Zero calls. The granted approval stays unspent because the budget rung precedes the consent port; a direct adapter send with that same port afterwards succeeds (1 call), which is the measurement that the refusal did not spend it. |
| Permission refusal | Zero calls, classified `OUTBOUND_REFUSED`. |
| Timeout | The fake hangs once; `asyncio.wait_for` bounds it; `ProviderTimeoutError` is classified TIMEOUT; the run records one issued-and-failed request. This path **does reach the substitute once** — §4.6 promises an explicit degraded path for timeout, not zero calls, and the record does not smooth that boundary over. Three consecutive timeouts fire Q7's first arm; a fourth case is refused before any new call (`endpoint.call_count` stays 3). |
| Unavailability | `FakeEndpoint(always_raises=...)` gives three real substitute failures; arm one fires on the third and the fourth case is stopped. |

Q7's two arms, both watched:

* **Three consecutive failed requests** — `CompoundStopLoss.record_failure`
  advances it; a success resets the counter. Removing the increment (M7)
  reddens `test_three_consecutive_failures_fire_the_first_arm_and_a_success_resets_it`.
* **Per-case proposal refusal rate above 50%** — one refused request in a
  one-request case is rate 1.0 and stops the run. Removing
  `OUTBOUND_REFUSED` from `PRE_WIRE_KINDS` (M6) makes the refusal count as a
  failure instead, arm two stays asleep, and its witness reddens. The
  trigger is raised as `StopLossTriggeredError` for the operator's loop to
  catch and record — Q7 says operator-watched, not an automatic retry.

## 5. Mutation ledger

Twelve counter-mutations, each applied to exactly one product module, one
witness run, then restored from `HEAD`. A mutation counts as effective only
when its named witness fails the assertion it watches — "DID NOT RAISE",
`AssertionError` or `Failed:` — and not a syntax, import or collection
error. Scripts: `run_mutations.py` and `run_rung_mutations.py` under
`E:\labcairn-local\tmp\p306-mut` (outside the repository).

| ID | Mutation | Witness | Result |
|---|---|---|---|
| M1 | n-gram verification removed | `test_a_surviving_material_run_refuses_the_whole_case` | RED |
| M2 | outbound CJK ceiling removed | `test_the_cjk_ceiling_holds_outbound_too` | RED (spot-checked: `Failed: DID NOT RAISE`) |
| M3 | named-secret check removed | `test_a_named_secret_copied_verbatim_is_refused` | RED |
| M4 | budget fail-closed removed | `test_a_budget_without_the_number_refuses_before_a_request_exists` | RED |
| M5 | per-excerpt digest comparison removed | `test_an_excerpt_port_bound_to_a_different_digest_does_not_leave` | RED |
| M6 | `OUTBOUND_REFUSED` no longer pre-wire | `test_a_per_case_refusal_rate_above_half_fires_the_second_arm` | RED |
| M7 | consecutive failures not counted | `test_three_consecutive_failures_fire_the_first_arm_and_a_success_resets_it` | RED |
| R1 | adapter budget preflight removed | `test_the_budget_ceiling_stops_the_run_before_the_wire_when_spent` | RED |
| R2 | probe-record gate disabled | `test_a_supplier_name_is_not_a_capability` | RED |
| R3 | consent bridge disabled | `test_a_pending_approval_refuses_without_reaching_the_substitute` | RED |
| R4 | capability refusal disabled | `test_an_unsupported_capability_refuses_before_the_wire` | RED |
| Q3 | whole-case digest precheck removed | `test_an_excerpt_port_bound_to_a_different_digest_does_not_leave` | RED |

**12/12 effective.** After every run the worktree was confirmed clean, so no
mutation reached a later measurement.

## 6. Sample class and fingerprint record format

Execution plan §4 names three classes; `SampleClass` names exactly those
three: `PUBLIC_SYNTHETIC` (CI and negative tests; every byte in these
witnesses is this class), `DEIDENTIFIED_DOMAIN` (the owner-authorised,
de-identified domain sample — the second class, and the one the real case
would run on), `AUTHORISED_TRIAL` (trial material, advisor use). The real
sample is **named but not promised**: no case in this work declares the
second class.

`SampleFingerprint` is the format the operator-side registry already uses
(111 `.docx` files fingerprinted 2026-11-09): lowercase sha256 hex digest,
byte size, class, aware UTC moment, short label. It refuses a free-string
class, a naive moment, an upper-case/short digest and a negative size. The
note is a label, never prose from the file — a fingerprint that carried the
file's opening sentence would be the leak it exists to prevent.

## 7. Local measurements

All on Windows 11 Pro 10.0.26300, CPython 3.12.13, the project venv at
`E:\LabCairn\.venv`. `PYTHONPATH` pointed at this worktree's `src` for the
witness runs (the editable install points at the main checkout). `TEMP`,
`TMP`, `TMPDIR` and `MPLCONFIGDIR` were set under
`E:\labcairn-local\tmp\p306-*` — outside the repository — and every
`--basetemp` lived there with no run sharing one. `COLUMNS=200` for the CLI
refusals. No status was read from a pipeline.

| What | Result |
|---|---|
| Two new test files, targeted | **33 passed** (13 unit + 20 integration) at `p306-c\bt1`. |
| Registration / reference-leakage / evaluation witnesses | **208 passed, 2 failed** at `p306-d\bt1`. The two failures are named in §8; the CJK table stayed at 49 files with no new entry. |
| `ruff check .` | exit 0 — `All checks passed!` |
| `ruff format --check .` | exit 0 — `530 files already formatted` (full-tree count reported by the command). |
| `mypy --strict src tests` | exit 0 — `Success: no issues found in 422 source files`. |
| Twelve counter-mutations | 12/12 RED for the intended assertion; worktree clean after each. |
| `scripts/witness_ledger.py 4855ea6 HEAD` | exit 0 — `LOST -- none`; 3528 test functions before, 3561 after (+33, the two new files). |
| Full local `pytest` | **6 failed, 5116 passed, 26 skipped** in 2065.73s at `p306-full\bt1`. Every failure is named and classified in §8; none is a failure of the new witnesses (all 33 passed within the full run). |
| Clean-room / outsider re-measurement, no `PYTHONPATH`, `UV_OFFLINE=1` | **127 passed**, exit 0, in 138.74s at `p306-h\bt1`. This covers `tests/test_no_reference_leakage.py` and `tests/test_outsider_path.py` together — including the five witnesses that failed in the full run for the shadowed-import reason and the fixture errors that the online re-run hit. |

## 8. Measured gaps and expected reds

1. **No runner number, no CI.** No push, no PR, no CI run (`CLAUDE.md`).
   The two new files carry `0.0` costs on both platforms — a placeholder
   saying "not measured", not a timing. The batch's own runner log and
   `python .github/remeasure_shards.py <run-id>` supply the real costs and
   `measured_at`.
2. **The shard freshness witness is expected red for a file this window did
   not touch.** `tests/test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on`
   reports `tests/test_application_layer.py` on `windows-latest` as changed
   since `fc6d65b64d5ff5a010d476725aca6b4660bccfa1`. That file was changed by
   LC-P3-03's landed batch; this window registered its own two files and
   changed none of `test_application_layer.py`. It is the commander's
   re-measurement, per the G1 precedent.
3. **Five measurement-method failures in the full run, and a second
   environment cause found while re-measuring them.** The full local `pytest`
   ran with `PYTHONPATH=<worktree>/src`, which the editable install needs for
   the 33 new witnesses to import the worktree's modules. That same variable
   pierces the clean-room witnesses:
   `test_no_reference_leakage.py::test_wheel_installs_clean_and_imports`
   resolves `labcairn` to the worktree's `src` instead of the throwaway venv,
   and four `tests/test_outsider_path.py` witnesses then see the same shadow
   in the clone's walk (`the walk ran the clone's own code`, `KeyError:
   'package'`, missing claims, `KeyError: 'not_exercised'`). None of the six
   failures is a failure of the new witnesses — all 33 passed inside that
   same full run.

   Re-running the same files without `PYTHONPATH` exposed a **different**
   environment failure, and it is reported rather than smoothed over:
   `uv build` in the reference-leakage probe project cannot resolve
   `hatchling` from `https://pypi.org/simple/hatchling/` (TLS handshake EOF
   after three retries), which produced 8 fixture errors and cascaded into
   the outsider walk's missing-claims assertions. That is an outbound network
   condition on this machine, not a property of the tree. With `UV_OFFLINE=1`
   the cached build works and the single clean-room wheel witness passes
   (1 passed at `p306-g\bt1`); the six sensitive tests together were
   re-measured offline without `PYTHONPATH`: **127 passed, exit 0** at
   `p306-h\bt1`, covering both files in one run. The three measurement shapes
   — full run with `PYTHONPATH`, online re-run without it, offline re-run
   without it — are kept separate, not reported as one green: the full run's
   6 failures and the online re-run's 6 failures + 8 errors are real results
   of their own conditions.
4. **No real call, no real sample, no installed build.** The real half stays
   gated on §4.8's right column: `LC-P3-04`'s proposal path, the
   de-identified domain sample's supply, the owner's credential file and
   `providers.json` on the trial machine, the real bill's usage accounting,
   and `LC-P3-05`'s installed build. Q5's `provider-smoke` GitHub secret
   stays uncreated this phase; the scheduled channel stays fail-closed.
5. **A person's review is not simulated.** The pipeline verifies a rendering;
   it does not rewrite one. The "One real model" row's locatable, reviewable
   suggestion and human review are not claimed here.
6. **No new refusal or recovery semantics.** The ladder is the adapter's
   existing gate, rehearsed; the harness adds the stop-loss and the record,
   not a second permission path.
7. **Checklist wording, kept exact.** `real_model_smoke = NOT RUN` and the 35
   unaccepted model-proposal edges are cited from their own Phase 2 records,
   not restated as current facts.
