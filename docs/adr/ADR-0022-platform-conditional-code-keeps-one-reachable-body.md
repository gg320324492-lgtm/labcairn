# ADR-0022 — Platform-conditional code keeps one reachable body on both checker platforms
**Line numbers.** The `file:line` pointers in this record name the lines as they stood on 2026-11-09; the tree has moved since. Follow the sentence, not the number.  
**Owner note (2026-11-09).** Drafted outside the checkout by an independent
agent session (a human reader was not performed), reviewed, and ratified into
the tree by the owner's selection the same day; the drafting provenance stays
recorded here because it is part of the decision's history.

**Status:** accepted (2026-11-09, owner ratification); implementation is on `main` in the commits this ADR cites
**Work order:** LC-P3-01 and LC-P3-02 (the Phase 3 G1 delivery batch, PR #153)
**Date:** 2026-11-09
**Drafted against:** local `main` at `571e4346a03374e166f3ab67d0067eb0e632dd52`
(`origin/main` equal; `git status --porcelain` 0 lines, printed separately)

## Live refs, re-printed at draft time

Every value below was printed read-only from the repository at drafting
time. The proposed number is **ADR-0022**; the newest ADR in the tree is
`ADR-0021-manuscript-editing-rewrite.md` (itself still `proposed`).

| Ref | Value |
| --- | --- |
| local `main` = `origin/main` | `571e4346a03374e166f3ab67d0067eb0e632dd52` (merge of PR #153, "Deliver the Phase 3 G1 batch") |
| first CI repair commit | `0a8d4bc3da5677fe18e4620e8b4bbc4d5ae9d87e` — "the platform guards are asked through a call, and the winreg uses are scoped" |
| second CI repair commit | `9dce56d316e3350ac16212fe6942bc88270701a4` — "the process-group flags helper refuses a platform without the constant" |
| third CI repair commit | `fc6d65b64d5ff5a010d476725aca6b4660bccfa1` — "the non-Windows process-group flags stay zero" |
| shard remeasure commit | `27763e9dcfccc2236f289c034f0da17f7dd47de1` — "the shard costs are re-measured from the batch's runner run" (run **42576918171**, measured at `fc6d65b…`, balance 1.000) |
| cost anchor now recorded | `.github/ci-shards.json` `measured_at` = `fc6d65b64d5ff5a010d476725aca6b4660bccfa1` |

Evidence files inspected read-only at drafting time (paths and the specific
helpers named in §Decision): `tests/workbench_serve_support.py`,
`src/labcairn/editing/evidence.py`, `tests/test_docx_edit_records.py`,
`tests/test_readme_accuracy.py`, `.github/remeasure_shards.py`,
`.github/ci-shards.json`, `pyproject.toml` `[tool.mypy]`, and the commit
bodies of the four commits above.

## Context and concrete problem

The Phase 3 G1 batch (LC-P3-01, the MAX_PATH repair, LC-P3-02) landed code
whose correctness depends on the platform: a Windows-only registry read
(`winreg.LongPathsEnabled`, the machine's path ceiling), a Windows-only stop
signal (`CTRL_BREAK_EVENT`), and Windows-only creation flags
(`CREATE_NEW_PROCESS_GROUP`). The natural shape — an `if sys.platform ==
"win32":` / `if os.name == "nt":` block guarding the Windows-only body
in place — is green on the Windows development machine and passes its own
tests there.

It is **red on the Linux runner**, for a reason that has nothing to do with
the property under test. mypy runs with `strict = true`,
`warn_unreachable = true` and `warn_unused_ignores = true`
(`pyproject.toml` `[tool.mypy]`), and **mypy constant-folds `sys.platform`
and `os.name` inside a module**: on a Linux checker, `sys.platform` is
`"linux"`, so a `sys.platform == "win32"` branch is judged statically
false and every Windows-only body after it is reported unreachable
(`import-unreachable`, `attr-defined`), and the Windows-only attribute
reads are reported as missing attributes. On the Windows checker the same
code folds the other way, so the defects are invisible where the code was
written and only appear where it is linted.

The damage reached **three jobs at once** (commit `0a8d4bc`'s message): the
`lint` job, and the two shards that carry the README-accuracy witness —
because that witness does not merely mention the commands, it **runs them**
(`tests/test_readme_accuracy.py` executes `uv run mypy` as one of the
README's commands, and asserts each exits 0), so a mypy error anywhere
reddens the shard that proves the README. The batch's delivery record
counts **six mypy errors across the three reddened jobs**; the per-error
list lives in the delivery session's records rather than in the tree, and
this draft treats *three reddened jobs* as the measured fact (it is what
the commit body records) and *six* as the delivery record's count,
unverified line-by-line by this draft.

Fixing it took **five runner rounds** before the batch could merge
(PR #153, merge `571e4346…`), reconstructed from the commit chain and the
delivery records:

1. Round 1 red: the constant-fold errors above. → `0a8d4bc` routes the
   guards through helper calls and scopes the ignores.
2. Round 2 red: the Linux runner now *reached* the flags helper at spawn
   time (the guard sits in the caller, exactly as intended) and hit a bare
   `AttributeError` on the Windows-only constant. → `9dce56d` makes the
   helper refuse loudly.
3. Round 3 red: the refusal **changed the runtime semantics** — the
   original spawn expression passed `creationflags=0` on every other
   platform, and raising broke that. → `fc6d65b` restores "return 0".
4. Round 4 red: the shard-cost witness, correctly, — the repairs had
   changed files under `src/` and `tests/`, so the costs no longer
   described the tree. → `27763e9` re-measures from the batch's runner
   run by the one command.
5. Round 5 green: merge allowed.

The pattern in the mistake is worth naming: **the code was written on the
platform whose checker cannot see the defect.** Nothing in the tree
explained the shape, so the next platform-conditional body would be written
the natural way and pay the five rounds again.

## Decision

**Platform-conditional code is written so that BOTH checker platforms see
the same reachable body.** Three rules, each anchored in the code as it now
stands on `main`:

1. **The guard is a call, not a comparison.** The platform question is
   routed through a helper function, so no checker narrows it away:

   - `tests/workbench_serve_support.py:505` — `_this_platform_is_windows()`
     ("**Compared through a function so no checker narrows it away.** A
     checker running on Linux constant-folds ``os.name`` … routing the
     question through a call keeps the runtime behaviour identical while
     every platform's checker sees the same reachable body."), returning
     `os.name == "nt"`.
   - `src/labcairn/editing/evidence.py:191` —
     `_this_platform_is_not_windows()` (`sys.platform != "win32"`), same
     docstring rationale.
   - `tests/test_docx_edit_records.py:141` — the same helper name, built on
     `os.name != "nt"`.

   A checker cannot constant-fold through the call boundary, so the
   Windows-only body stays "reachable" everywhere, and the runtime
   behaviour is identical to the in-place `if` it replaced.

2. **Windows-only attribute reads carry scoped ignores, at the use site.**
   `winreg` and the Windows-only `subprocess`/`signal` constants exist on
   Windows only, so each use site names exactly the error codes the other
   platform's checker reports, and nothing wider:

   - `src/labcairn/editing/evidence.py:214` —
     `import winreg  # type: ignore[import-unreachable,unused-ignore]`;
     `:218-222` — the `OpenKey` / `HKEY_LOCAL_MACHINE` / `QueryValueEx`
     reads carry `# type: ignore[attr-defined,unused-ignore]`.
   - `tests/test_docx_edit_records.py:185` (import), `:187-191` (the same
     three attribute reads), and the second probe at `:216`.
   - `tests/workbench_serve_support.py:524` —
     `signal.CTRL_BREAK_EVENT  # type: ignore[attr-defined,unused-ignore]`;
     `:539` — `subprocess.CREATE_NEW_PROCESS_GROUP  # type:
     ignore[attr-defined,unused-ignore]`.

   The `unused-ignore` half is deliberate: on a Windows checker those
   ignores are unused, and `warn_unused_ignores = true` would flag them —
   so the ignore is scoped to both codes, and a future removal of the
   Windows-only read leaves a visible stale-ignore instead of silence.

3. **Runtime semantics are preserved exactly; the repair never changes what
   the program does.** The Windows-only body must answer, on every
   platform, what the original in-place expression answered:

   - `_windows_process_group_flags()`
     (`tests/workbench_serve_support.py:528`) **returns 0 on a platform
     without the constant** — the original spawn expression passed zero
     there, and `fc6d65b` restored exactly that after `9dce56d` had
     (over-)replaced it with a refusal. The helper's docstring records why:
     "the original spawn expression passed zero elsewhere, and the helper
     keeps that runtime answer".
   - A **loud refusal is reserved for a call that was already wrong**:
     `_long_paths_enabled_windows` is only ever called behind the platform
     guard, and a wrong-platform call there is a caller defect worth
     exposing — but that is a statement about the *caller's* contract, not
     a licence to change an expression's semantics during a type-repair.
     When in doubt, preserve the original value (`0`, `"unknown"`) and say
     so in the helper's docstring.

**Consequences — the shape every future platform-conditional body follows:**

```python
def _this_platform_is_windows() -> bool:
    """Whether this host is Windows, asked through a call.

    **Compared through a function so no checker narrows it away.** …
    """
    return os.name == "nt"


def _windows_only_thing() -> X:
    """The Windows-only half; the caller holds the platform guard.
    """
    if not _this_platform_is_windows():
        return <the original non-Windows answer>   # exact original semantics
    value: int = WindowsOnlyModule.CONSTANT  # type: ignore[attr-defined,unused-ignore]
    return value
```

**And the shard-cost consequence is already in force:** changing any file
under `src/` or `tests/` re-reddens the shard-cost witness by design, and
the fix is never a hand-edited number — it is
`python .github/remeasure_shards.py <run-id>` reading the per-file seconds
out of a runner's log (`.github/remeasure_shards.py` header: "every number
in the table comes from a runner, because **a development machine gives a
different answer** — not only a different total, a different *order*").
The batch's repair rounds demonstrate the sequence end to end: commit
`27763e9` re-measured from run 42576918171, anchored the costs to
`fc6d65b…`, and rebuilt both platforms' partitions at balance factor 1.000.

## Alternatives considered and rejected

- **In-place comparison guards** (`if sys.platform == "win32":` /
  `if os.name == "nt":` guarding the body in place). This is the shape the
  batch originally shipped, and it is what round 1 measured: the Linux
  checker folds the comparison, judges the body unreachable, and reddens
  the lint job and both README-accuracy shards. Rejected by measurement,
  not by taste. (An `assert sys.platform == "win32"` guard is the same
  defect in a different costume: the checker narrows on the assert, the
  interpreter drops it under `-O`, and the runtime guard is gone precisely
  when the static one is being relied upon.)

- **Host-wide allowlist — a per-platform mypy override or a global
  relaxation instead of scoped ignores.** Rejected for the reason the
  project's own `pyproject.toml` already records for the library
  overrides (`[tool.mypy]` comment, lines 299–302): "the alternative is a
  global relaxation that also hides real errors elsewhere." A
  platform-conditional override is worse than a global one here: the lint
  job runs on Ubuntu only, so an override tuned for the Windows checker
  would make every Windows-only defect invisible to the one job that lints,
  and the errors would surface only as runtime failures on a runner that
  never runs them.

- **Loud refusal where the original passed a value** (the `9dce56d`
  intermediate: `hasattr`-gate the constant and raise otherwise). Rejected
  by round 3's measurement: it reads as a hardening and is actually a
  semantic change — the original expression passed `creationflags=0` on
  non-Windows, so raising changed what a correct call does. The rule that
  survives is §Decision rule 3: semantics are preserved exactly, and
  refusal is a caller-contract question, decided where the caller's
  contract is defined, not smuggled in by a type repair.

## Risks, tradeoffs and reversibility

- **Three-line cost per site.** Each platform-conditional body now costs a
  guard helper, a split-out half-function, and a scoped ignore. That is the
  price of both checkers seeing the same body; it is small, but it is real,
  and a reviewer who does not know the rule will "simplify" it back to the
  in-place `if` and re-import the defect. The witness in §Contracts exists
  to make that simplification visible.
- **The ignores are load-bearing on Linux and dead on Windows.** On a
  Windows checker `unused-ignore` fires if the Windows-only attribute is
  ever removed — which is the desired behaviour (a stale ignore is a
  signal), but it means these lines will redden on Windows during any
  refactor that touches the guarded attribute, and the fix is to update the
  ignore together with the code, not to widen it.
- **Reversibility is high.** The shape is local (three helpers, three
  files, no contract change); reverting it restores the original
  in-place guards and nothing else. What is not reversible cheaply is the
  *convention*: once future code stops following the shape, the five-round
  lesson is re-paid one body at a time.

## Contracts and acceptance tests

- **The lint job must stay green on Ubuntu** while the Windows bodies
  remain genuinely used on Windows. Witness today: the `lint` job itself
  (`ruff check .`, `ruff format --check .`, `mypy` on Ubuntu), and the
  README-accuracy witness, which executes `uv run mypy` as a README
  command and fails when it exits non-zero
  (`tests/test_readme_accuracy.py`, `test_readme_commands_run`).
- **The runtime answers must not drift.** Witness today:
  `tests/test_docx_edit_records.py` drives the probe's non-Windows skip and
  monkeypatches `winreg.QueryValueEx` to watch the Windows half;
  `tests/test_workbench_serve_helper.py` watches the helper's spawn and
  stop arrangement, including the process-group flags reaching
  `subprocess.Popen`.
- **A value that can change is re-measured, not carried forward.** Witness
  today: `tests/test_ci_shard_coverage.py`, which fails when the recorded
  costs no longer describe the tree; the repair is the remeasure command
  with a runner run id, demonstrated by commit `27763e9`.
- **A future witness to add (this draft asks the owner for it, and adds
  nothing itself):** a small structural witness that fails when a
  `sys.platform`/`os.name` *comparison* appears as a module-level guard
  condition directly protecting a Windows-only import or attribute read —
  so the shape itself is watched, not merely remembered. The four
  repaired sites are the examples a mutation check would target (revert
  one helper to an in-place comparison and the witness must redden). Until
  such a witness exists, the convention is guarded by review only, which
  this project's own rule says is not a guard.

## Re-evaluation trigger

Re-open this ADR if any of these change:

- mypy stops constant-folding `sys.platform`/`os.name` at module level, or
  grows a supported platform-model option (then the helper-call dance
  becomes unnecessary and should be retired);
- the lint job starts running on more than one platform (then rule 2's
  `unused-ignore` halves may need per-platform decisions re-examined);
- a third checker platform joins the gate (the rule is stated for two, but
  the mechanism — guard by call, scoped ignore, preserved semantics —
  extends by adding the third platform's reachable body, and the wording
  should be generalised then, not before).
