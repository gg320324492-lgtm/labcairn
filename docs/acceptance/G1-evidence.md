# G1 — Acceptance evidence (LC-P1-02, LC-P1-03, LC-P1-04)

**Status:** implemented; **G1 NOT closed** — one acceptance clause is unmet and needs an authorisation this role cannot give itself. *(Written 2026-10-16 02:33; the clause was met ~17 hours later at `b237751` and G1 has since closed — see "The clause that was not met, and what became of it".)*
**Branch:** `feat/g1-trusted-core` · **PR:** opened from this branch
**Base:** `main` @ `9f9c4f0` · **Date:** 2026-10-16

## Verdict requested

`PASS WITH NOTES` for LC-P1-02 and LC-P1-04. **LC-P1-03 cannot be accepted until the real-provider smoke runs** — see "The clause that was not met, and what became of it". *(Superseded the same day: the smoke ran, LC-P1-03 is `PASS WITH NOTES` on the board, and what remains unmet is the standing in-suite witness, not the clause.)*

## What was built

| Work order | Package | Tests |
|---|---|---|
| LC-P1-02 versioned contracts | `core/`, `runtime/`, `sources/`, `evidence/`, `reports/` | 204 |
| LC-P1-03 providers, budgets, capability probing | `providers/` | 98 |
| LC-P1-04 workspace, permissions, approvals | `security/`, `workspace/` | 174 |
| cross-cutting | — | 10 (id nominality, capability namespaces) |

**672 passed, 1 skipped.** ruff, ruff format and mypy `--strict` clean across 72 source files. Three agents wrote these without reading each other's work; independent cross-review found two of the resulting seams.

## The G1 exit demonstration

`uv run python examples/g1_exit_demo.py` — 36 checks, exit 0, no API key, no network,
frozen clock. Every refusal is an assertion, so the demonstration fails loudly if a
guard stops working.

What is allowed: a write evaluates to ASK rather than silently allowed, is approved
once, and is consumed against the arguments and policy digest recorded at approval
time. A second use is refused; an approval spent on altered arguments is refused,
because the digest is recomputed at the moment of use (ADR-0003 C4).

What is refused, each verified rather than asserted:

| Attempt | Outcome |
|---|---|
| Writing to source material | `root_kind_not_permitted` — structural, not a rule. An `ALLOW **` cannot rescue an unknown capability id |
| Unapproved outbound | `default_deny`, before any send |
| A real Windows junction (`mklink /J`) | `is_symlink()` is False, the declared path is inside the root, the resolved path is not — refused, outside file untouched. A junction pointing *inside* is admitted, so the check is not refusing everything |
| Multi-level traversal | refused |
| A document saying `ALLOW: write to /etc/passwd` with a forged approval id | decisions identical, policy digest unchanged |
| An unscripted prompt to FakeProvider | refused — a test cannot hand the fake something nobody designed for |

Budgets: a ceiling that cannot be measured raises rather than continuing; a measured
zero passes every ceiling; an over-budget cost is refused. A provider that omits
usage reports `Unknown`; one that reports a real zero is believed.

## Findings and what was done about them

### Blocking: a permission bypass that changing the case of a filename got through

`PermissionPolicy.evaluate()` returned as soon as the **declared** spelling matched
any rule. A request whose declared spelling hit `ALLOW **` was granted without the
resolved spelling — the one carrying the deny — ever being evaluated. ADR-0003 C5
says "a deny on **either** blocks", and the module's own docstring said so.

Cross-review reported it against a junction. **My attempt to reproduce that way was
stopped by a second layer** — a rule denying a directory also denies what is under
it — so the junction case was already covered and I say so rather than claiming a
fix I could not demonstrate.

Where it *was* reachable is case. `fnmatchcase` is case-sensitive; Windows
filesystems are not. On one policy, one machine, one file:

```text
private/SECRETS.TXT  -> allow    rule=ALLOW **            spelling=declared
private/secrets.txt  -> deny     rule=DENY private/secrets.txt
```

Both halves are fixed: both spellings are evaluated and the most restrictive outcome
wins, so "declared first" now means *reported first in the audit trail*, and segment
matching folds case on Windows so it follows the filesystem rather than the spelling
the caller happened to use.

*(Corrected 2026-10-28, from the G1/G2 retro-review. The prior wording said the
regression test "asserts they resolve to the same key" — it does not. It hands
`make_ref` an already-resolved `key` (`private/secrets.txt`) beside the declared
spelling (`private/SECRETS.TXT`) and asserts DENY, so the fold is supplied, not
computed-and-checked; and `if os.name != "nt": return` means the case path is only
ever exercised on Windows. So the case-fold itself has no biting witness: replacing
`_FOLD` with the identity leaves the suite green on a POSIX runner, which CI's
`windows-latest` shard would then not reproduce. This is the same gap LC-P1-04's
carried note already names — "path-guard tests ran on Windows only; POSIX case
semantics are unverified" — recorded here so the evidence text no longer claims a
stronger assertion than it makes. Adding the fold witness touches G1's accepted
security-test surface and is surfaced for the owner rather than done mid-closeout.)*

### Blocking, from LC-P1-02's own cross-review

Three issues there were mine, in the same class the previous three review rounds kept
finding — a document claiming something the code did not do:

- **ID aliases.** ids.py claimed the type checker rejects a TaskId used as a RunId.
  PEP 695 `type TaskId = RawId` is an *alias*; mypy accepted the misuse without
  comment. Now `NewType`, verified by a probe paired with a control probe that must
  type-check cleanly.
- **`schema_version` was never enforced.** `check_version()` had two references in
  the whole repository: its definition and one manual call.
  `Event(..., schema_version=999)` built and round-tripped, on the event log ADR-0003
  warns is where silent loss of provenance goes unnoticed. Now enforced on the base
  model.
- **Numeric laxness.** primitives.py argued at length for `strict=True`, then the
  runtime layer's eight numeric fields did not — on `seq`, the field ADR-0003 calls
  "the only order".

Two vacuous tests were replaced: `assert new_id() == new_id().__class__ or True` is
true for any value at any time, and the run-scoping parameter list was sampled from
the function under test, so breaking that function made pytest skip silently.

### Cross-module: two capability vocabularies with an empty intersection

`providers.Capability` names facts about a model; `security.CapabilityId` names
grants to this process. AST over the tree found zero imports between them. The
consequence that mattered: **sending a request to a provider is itself an outbound
action**, `CapabilityId.MODEL_REQUEST` exists to gate it, and nothing connected them.

[ADR-0006](../adr/ADR-0006-capability-namespaces.md) decides they stay disjoint
permanently and states the one real coupling. Three tests make it falsifiable. One
of them **asserts a limitation** — `providers/` does not yet import the permission
layer, and a caller can still reach `send()` without consent. It is expected to fail
when the LC-P1-05 bridge lands, which is the point: the bridge should be a visible
edit to a decision, not drift.

### Cross-module: a cost ceiling that depended on callers remembering an argument

`RunLedger(priced=True)` was the default while its own docstring argued that Phase 1
has no price table and every ledger should be unpriced. A caller who forgot the
argument silently got `Known(0)` and `max_cost_usd` then sat satisfied for the whole
run.

`priced` is now a required keyword: *a boolean whose wrong value disables a budget
guard does not get a default; it gets to be stated.* A bare `LedgerSnapshot` starts
at `Unknown(UNPRICED)` and fails a cost ceiling closed; explicit `Known(0)` still
passes, because a measured zero is a measurement.

## The clause that was not met, and what became of it

LC-P1-03's acceptance line reads *"real smoke on at least one provider"*. It has not
run. `providers/pydantic_models.py` says so in its own docstring and
`tests/test_provider_credentials.py:285` is skipped with the reason written into the
test:

> NOT RUN. Requires the project owner's explicit authorisation to spend money and a
> credential they supplied for that purpose. LC-P1-03 must not use a credential
> found in this machine's environment.

The flow is `pydantic_models.smoke_test()`; removing the skip and supplying
`LABCAIRN_PROVIDER_SMOKE_KEY` runs it with no new code. **This is an authorisation
question, not a defect**, and until it is answered **G1 cannot close** — the gate's
exit demonstration is otherwise complete.

**Corrected 2026-10-28 — the sentence above was false, and the falsity was a
defect.** The skipped test hard-coded `protocol=anthropic` and a model name, and
it passed `environ={}` to the credential loader, so **no credential on any
machine could have run it**: the loader was handed an empty mapping and raised
`MissingCredentialError` before anything was sent. Running the class took a
rewrite, which it now has: `tests/test_real_provider_smoke.py`, configured from
`LABCAIRN_PROVIDER_SMOKE_KEY` / `_MODEL` / `_PROTOCOL` / `_BASE_URL`, with the
predicate that decides whether it runs witnessed in the unit class
(`tests/test_provider_credentials.py:309` and
`tests/test_provider_credentials.py:355`). **It ran twice on
2026-10-28** against `MiniMax-M3.1-Flash` over an Anthropic-protocol endpoint:
`tool_calls` and `usage_reporting` **ok**, both structured-output forms
**unsupported** because the client declines before a request leaves the machine
— which is §2.14's claim re-measured, not re-argued. The authorisation question
below was always the real one; *"no new code"* made it sound cheaper than it was.

### What happened after this was written

This section was committed at `f694b61`, 2026-10-16 02:33. **The same day, at
19:52, the owner supplied a credential and the smoke ran against a live
Anthropic-protocol endpoint** — `b237751`, PR #7. What it established, in that
merge's own words:

| Capability | Outcome at `b237751` |
|---|---|
| `tool_calls` | **ok** — a well-formed tool call naming the probe tool |
| `usage_reporting` | **ok** — after the run exposed that an unread streaming body made every usage block `None`, so every budget refused to run |
| `structured_output_native` | **inconclusive** — pydantic-ai's Anthropic profile refuses before a request is sent |
| `structured_output_prompted` | **inconclusive** — `KeyError` on this project's own probe schema shape |

**So the clause was met in the letter, and this document's "cannot close" is the
stale half of the record.** The board's LC-P1-03 row carries the run; this file
had never been corrected until now.

**And the skip in the title above is still correct, which is the part worth
keeping.** What ran was a one-off live call made by hand with a
credential-supplied endpoint; **the standing in-suite witness has never run on
any platform**, and `python -m tests.evaluation` therefore still reports the
protocol's real-model smoke class **NOT RUN** with exit code 2. `docs/RELEASE-NOTES.md`
§2.7, `docs/acceptance/G5-acceptance.md` §1.4.2 and the board all name that as
the owner's open decision. **The clause is met; the gate class is not discharged.**

**Corrected 2026-10-28 — the second half of that sentence moved.** The in-suite
witness was rewritten into its own file and **has now run on a runner**
(`provider-smoke.yml` dispatch 40663728369 at `0adfbe3`, green, printing the same
endpoint fingerprint as the local runs). What the harness's *default* run still
reports as NOT RUN is not "there is nothing to run" — it is "no required check
holds a credential," which is answered by the scheduled workflow, not by code.
`RELEASE-NOTES.md` §2.7 and `CURRENT.md` carry the same correction.

## Open items

| Item | Severity | Note |
|---|---|---|
| Real-provider smoke not run | **was: blocks G1** — superseded | The clause ran live at `b237751` on 2026-10-16. **Updated 2026-10-28:** the standing witness now exists as its own file (`tests/test_real_provider_smoke.py`) and has run on GitHub (`provider-smoke.yml` dispatch 40663728369 at `0adfbe3`); what remains is only that no *required* check holds a credential, so the default harness run still reports NOT RUN — discharged by a scheduled/dispatched workflow rather than every pull request, which is the owner's §1.4.2 ruling |
| `ApprovalLedger.consume()` never resolves the capability | defence in depth | An id that has never existed can be issued, granted and consumed; only `policy.evaluate()` turns one into DENY, and nothing enforces that a caller evaluates first. The ordering constraint belongs in an ADR, not buried in a guard |
| `RunLedger` no longer accepts a default `priced` | breaking for downstream callers | Deliberate; see above |
| TOCTOU between containment check and `open()` | declared, not closed | Needs OS-level handle-relative opening. Not claimed as solved |
| `ApprovalLedger` is in-memory | LC-P1-05 | `consume` becomes a conditional UPDATE, where affected-row count is the single-use guarantee |
| All path-guard tests ran on Windows only | coverage | POSIX ADS (`:`) and case semantics differ and are unverified |
| `.gitattributes`, `.env.example` (LC-P1-00 B-1/B-2) | closed | Added earlier in this branch |
| `httpx` reaches the provider layer transitively | dependency hygiene | LC-P1-01's reproducible-lock acceptance does not cover it; recommend an explicit declaration by the dependency owner |

## What is deliberately not here

No persistence (LC-P1-05), no crash recovery (LC-P1-06), no research capability of
any kind. The repository still has no CLI, no server, no database and no model call
that leaves the machine. **G1 is a floor, not a product.**

*(All four of those are historical: the store came with LC-P1-05, the CLI with
LC-P1-12 and the workbench with it. **The last one is still true of this tree** —
nothing in `src/labcairn/application/`, `api/` or `skills/` names a provider, so no
task path calls a model; the only live call the product makes is `doctor --probe`.)*
