# G1 — Acceptance evidence (LC-P1-02, LC-P1-03, LC-P1-04)

**Status:** implemented; **G1 NOT closed** — one acceptance clause is unmet and needs an authorisation this role cannot give itself.
**Branch:** `feat/g1-trusted-core` · **PR:** opened from this branch
**Base:** `main` @ `9f9c4f0` · **Date:** 2026-10-16

## Verdict requested

`PASS WITH NOTES` for LC-P1-02 and LC-P1-04. **LC-P1-03 cannot be accepted until the real-provider smoke runs** — see "The clause that is not met".

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
the caller happened to use. A regression test constructs both spellings as one file
and requires DENY, first asserting they resolve to the same key so it cannot pass
for the wrong reason elsewhere.

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

## The clause that is not met

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

## Open items

| Item | Severity | Note |
|---|---|---|
| Real-provider smoke not run | **blocks G1** | Needs spending authorisation and a credential issued for the purpose |
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
