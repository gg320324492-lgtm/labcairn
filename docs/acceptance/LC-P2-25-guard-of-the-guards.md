# LC-P2-25 — The guards of the guards

**Status:** CLOSED — two carried Phase 1 debts, each with a witness of its own.
**Date:** 2026-11-02.
**Branch:** `claude/sad-wright-a38d26` (worktree `sad-wright-a38d26`).
**Carried from:** `docs/plans/PHASE_2-work-orders.md` §5, the row *"The Gitleaks
allowlist guard is textual, and the README capability-claim detector has known
holes"* — "both are stated floors, not truth-checkers".

Each weakness was reproduced against the unmodified tree before anything was
changed, and each fix has a witness that fails when the guard is mutated.

## 1. The Gitleaks allowlist guard

### The weakness, demonstrated

The old `test_gitleaks_config_declares_no_path_allowlist` parsed the config but
enumerated only the top-level `allowlists` array; everything else was a text
fallback that looked for `path` and a reference-family stem on the same line.
Calling the real test function with a temporary `repo_root` holding each
crafted config produced:

```
BYPASSED top-level [allowlist] + multiline paths
BYPASSED [[rules.allowlists]] + multiline paths
CAUGHT   [rules.allowlist] paths          (same line: "paths" + "_references")
CAUGHT   rule inline-table allowlist      (same line: "paths" + "_references")
```

Two path exemptions were therefore accepted. The second is the one the debt
row names: the multi-line array splits `paths` from `_references`, and the
nested array is never enumerated.

### What gitleaks 8.30.1 actually honours

The pinned binary is on this machine (8.30.1, the version CI downloads). A
throwaway git repo with one synthetic `SECRETTOKEN12345` finding under
`_references/` was scanned with each config variant; exit code 0 means the
allowlist suppressed the finding, 1 means it did not:

| Allowlist shape | 8.30.1 | Old guard | New guard |
|---|---|---|---|
| top-level `[[allowlists]]`, multi-line `paths` | suppressed | caught | caught |
| top-level `[allowlist]` (singular) | suppressed | **bypassed** | caught |
| `[[rules.allowlists]]`, multi-line `paths` | suppressed | **bypassed** | caught |
| `[rules.allowlist]` | suppressed | caught (line fallback) | caught |
| rule `allowlist = { ... }` inline table | suppressed | caught (line fallback) | caught |
| top-level `allowlist = { ... }` inline table | not honoured | bypassed | caught defensively |
| no allowlist (control) | finding | — | — |

The top-level inline table is inert in 8.30.1, but the guard refuses it anyway:
being stricter than the tool costs nothing, and a future version that honours
the shape would already be covered.

### The fix

`_gitleaks_allowlist_offenders(text)` parses the file with `tomllib` and walks
every allowlist the schema has a place for: top-level `allowlist` /
`allowlists`, and each rule's `allowlist` / `allowlists`, whether written as a
table, an array of tables, a multi-line array or an inline table. Any `paths`
entry is an offender; any exemption without a `description` is an offender too
(the earlier rule required a description only of the top-level array). The
line fallback remains as a last resort for a shape the walk does not name yet.

`test_gitleaks_config_declares_no_path_allowlist` now calls this function, so
the live config and the probes share one definition of the rule.

### Witnesses

- `tests/test_no_reference_leakage.py::test_gitleaks_guard_sees_every_allowlist_shape`
  — seven parametrized configs, one per shape above, including the two the old
  guard accepted and the undocumented nested regex exemption.
- `tests/test_no_reference_leakage.py::test_gitleaks_guard_still_accepts_the_repository_config`
  — the live `.gitleaks.toml` with its two narrow, described exceptions is
  still accepted.
- The existing `test_gitleaks_config_declares_no_path_allowlist` stays green on
  the live config.

### Mutation check

| Mutation | Result |
|---|---|
| stop collecting each rule's `allowlist` / `allowlists` | **2 failed** among the shape cases (nested multi-line array, undocumented nested regex) |
| stop collecting the top-level singular `[allowlist]` | **1 failed** (the singular multi-line case) |
| restore | all green |

## 2. The README capability-claim detector

### The weakness, demonstrated

`docs/acceptance/LC-P1-01-evidence.md` lists the open holes: passive voice
("is supported by"), "is capable of", "handles", "can", "has a built-in",
"comes with", and the Chinese modals 可以 / 能 / 用于 / 现可使用. One sentence
per form was run through `find_unsupported_claims` on the unmodified tree:

```
missed 11 of 11
```

Every listed form was invisible to the detector. The active-verb trigger had no
branch that could match any of them.

### The fix

`_TRIGGER_RE` gains one branch per listed form. English branches are
word-bounded. The Chinese 能 is excluded inside the compounds that make it a
noun (能力 / 性能 / 功能 / 可能 / 智能 / 本能 / 能耗 / 能源) and in the negations
不能 / 能否; the latter was found by running the hardened detector over the
README, whose sentence "本 README 不能替代许可证" would otherwise have been
read as a capability claim.

The detector is still a floor, not a proof: the new branches close the forms
the record names, and no further claim is made.

### Witness

`tests/test_readme_accuracy.py::test_claim_detector_catches_forms_recorded_as_open_holes`
— the eleven sentences above, one per recorded form, each of which returned no
finding before this change. The existing `test_claim_detector_has_teeth` and
`test_readme_makes_no_unqualified_capability_claim` remain green; the README
itself is byte-for-byte unchanged.

### Mutation check

Replacing every added trigger branch with a never-matching one makes the
witness fail (1 failed); restoring makes it pass.

## Verification

Local runs only. No CI run was started and no pull request was opened, per the
owner's 2026-10-24 rule.

| Check | Result |
|---|---|
| six target tests (both guards, old and new witnesses) | 12 passed |
| `tests/test_readme_accuracy.py` | every non-network test passed; the two `uv`-driven commands fail resolving `hatchling` because PyPI is unreachable from this machine (`tls handshake eof`), before any detector assertion runs |
| `tests/test_no_reference_leakage.py` | 99 passed, 8 errors — every error is `uv build` failing to fetch `hatchling` for the same network reason |
| full `mypy` (strict, `src` + `tests` + `conftest.py`) | exit 0 |
| `ruff check .` | clean |
| `ruff format --check .` | 414 files already formatted |

The changed files are under `tests/`, so `tests/test_ci_shard_coverage.py` will
report the shard costs as measured at an older commit. That is the project's
rule (*a value that can change is re-measured*) and needs a runner; it is not a
failure of this change.

## What this does not establish

- **The qualifier whitewash was closed on 2026-11-03, in commit
  `1d28aa325ba2195c9bdf604e9841fa51d0306e1f`.** `_QUALIFIER_RE` used to
  exempt a whole sentence that contained `target` / `intended` / `future` /
  `目标` / `拟` / `将(?:会|要)?`, so a planning word could launder a
  present-tense claim in the same sentence. The exemption is now
  **clause-scoped**: a new `_CLAUSE_SPLIT_RE` splits a sentence on commas,
  semicolons, colons (ASCII and full-width), em dashes, conditioned English
  `and` / `or` / `but` (a subject or verb-like word must follow — an
  unconditional split would cut the noun list in "DOCX and PDF support"), and
  unconditioned Chinese adversatives 但 / 不过 / 然而, and
  `_needle_clause_unqualified` exempts only clauses that carry the planning
  word themselves. The qualifier table also gained the planning verbs it never
  had (打算 / 试图) and the negated-assertion markers (不声称 / 不宣称 /
  does not claim / makes no claim), because a sentence that denies the
  capability is not claiming it. The capability check, the licence-grant check
  and the released-status check now all go through the same helper, and
  `test_a_planning_qualifier_covers_its_clause_not_the_whole_sentence`,
  `test_a_qualifier_cannot_launder_a_licence_grant` and
  `test_a_qualifier_cannot_launder_a_release_status_claim` are the witnesses;
  `test_readme_makes_no_unqualified_capability_claim` carries the same rule
  over the README itself. Mutation checks: replacing the clause split with the
  whole sentence fails all three; dropping the negated-assertion markers or
  the Chinese adversative splits fails the capability witness.

  **The false-positive cost was measured before the change, at commit
  `15faa4bd6e5fc145ac34549c1ae4a2b2aaa10305`, on the surfaces the guard
  actually reads** (the README prose and every synthetic witness sentence):
  nine laundering probes the whole-sentence rule exempted are all reported by
  the clause-scope rule; nine honest planning sentences all stay clear; the
  grant and released-status surfaces take no new findings on the README; and
  every existing synthetic witness keeps its verdict. The narrowing adds
  **exactly one** README finding — the Chinese vision sentence whose
  `让……能够` clause states a purpose, not a capability — judged a false
  positive, and settled on the README side by the smallest equivalent wording
  (`能够定位来源` → `可定位来源`, matching the 可检视 / 可复现 pattern the
  next sentence already uses), in both README.md and README.zh-CN.md. The
  adjusted README takes zero findings under the narrowed rule. The measured
  residual: an unqualified laundering clause inside parentheses, or after a
  connector the split does not know, still hides behind a plan word elsewhere
  in its sentence — the split is a boundary list, not a parser.
- **The detector remains a floor.** The eleven closed forms are the ones the
  Phase 1 record lists. A new phrasing outside both trigger groups is still
  invisible.
- **No runner has measured this branch.** The numbers above are local, as the
  record requires them to be labelled.
