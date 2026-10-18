# ADR-0011: Match the policy on the canonical entry, not the declared spelling

**Status:** Accepted and **ratified by the project owner** — records the execution of ADR-0003 §C5, changes no contract
**Work order:** LC-P1-08 (material inventory and source locators)
**Date:** 2026-10-18 · ratified 2026-10-18

> This ADR does not change a contract. It records how ADR-0003 §C5 is
> *executed* at two points where the execution did not match the rule.

> **Ratified 2026-10-18.** Unlike ADR-0010, this one amends nothing, so the
> ratification is narrower: it approves *how* §C5 is executed, not §C5. It does
> not re-open ADR-0003, and it does not extend the boundary — every change here
> makes the code do what the frozen contract already said.
>
> It was merged in PR #29 under `mergeStateStatus=CLEAN` with twelve checks
> green on both Ubuntu and Windows, and ratified afterwards.
>
> **What ratification covers.** The canonical listing check, the protected read,
> `read` remaining the unchecked primitive, and `SourceAccessDeniedError` being
> distinct from `SourceIsReadOnlyError`. It does not close the items below.

## Context and concrete problem

ADR-0003 §C5 says a denied entry is filtered out of a listing, and that
**both spellings** of a path are matched. §C5's own reasoning is that the
model must never learn a denied name existed.

The implementation matched only the **declared** spelling.

`policy.filter_listing` built each entry as:

```python
ResourceRef(declared_key=key, resolved_key=key, ..., real_path=real_root / Path(*key.parts))
```

Both spellings were the same string and the path was joined, not resolved —
so a symlink was judged by its name and by nothing else. And
`SourceMaterial.read` checked *whose* material it was (`root_kind is
SOURCE`) and never consulted the policy at all, by design: the policy is
applied by the tool layer above.

The consequence was demonstrated, not theorised. With
`DENY source.inventory private/**`, and a symlink `public/hop -> private`:

```
list_dir('public')        ->  ('public/hop', 'public/ok.md')
read('public/hop/secret.md') ->  b'# SECRET\\r\\nlaunch codes\\r\\n'
```

The deny rule did not stop it, and neither did `DENY private/secret.md` nor
`DENY **/secret.md`. Only a blanket `DENY **` did. The repository treats
junctions separately from symlinks, and a directory junction leaked the same
way.

LC-P1-08's workspace walk is what turned this gap into **persisted,
searchable rows** — it was the first code path that would read a denied file
and store its text. So the gap became a defect of the walk, and the walk's
docstring asserting the opposite made it worse: a reader checking whether
ingestion respected the boundary would have been told yes.

## Decision

**Two checks, and the second does not depend on the first being right.**

1. **The listing evaluates the policy on the canonical entry.**
   `filter_listing` takes an optional `resolve` callback; `SourceMaterial.list_dir`
   supplies one built from `Workspace.path_in`, so each entry is judged on the
   path the filesystem will actually open, with both spellings in the
   `ResourceRef` as §C5 requires. Callers with no workspace to resolve
   against keep the old behaviour, which is only sound for entries that
   cannot be symlinks.

2. **A protected read evaluates the policy before opening.**
   `SourceMaterial.read_permitted` resolves the entry, evaluates the
   capability, and refuses on a denial with a new
   `SourceAccessDeniedError` — distinct from `SourceIsReadOnlyError`, which
   is about *writing*, because a caller that converts path errors into tool
   errors should not swallow a policy outcome.

   `read` stays as it was: the unchecked primitive. It now **says** that it
   does not consult the policy, and points at `read_permitted`. A caller that
   reads denied material is not misusing `read`; it is using it correctly and
   skipping the check that was its own job.

The workspace walk uses `read_permitted`. Defence in depth is the point: the
listing could be wrong again, and ingestion should not then store a denied
file's bytes.

## What this costs

- `filter_listing` gains a parameter and `list_dir` gains a closure. The
  canonicalisation costs a `Path.resolve` per listing entry — on a large
  workspace, a per-entry syscall that a listing did not previously pay.
- `read_permitted` is a **refusal**, not a filter. A single named read has
  no "drop it from the results" to do, so a denial is an error. Callers
  that want the old behaviour still have `read`.
- The walk's **failure report is unchanged in the case this ADR is about**.
  A denied symlink is dropped by the listing, so the walk never visits it and
  never records anything for it — the report stays as it was, listing fewer
  files. `WalkReport.failures` would gain an entry only if an entry the
  listing permitted were refused at read time, which for these rules means a
  workspace changing underneath the walk. This was measured rather than
  assumed; the earlier draft of this section claimed the walk reports the
  denial, and that is not what it does.

## Contracts and acceptance tests

1. A symlink inside a permitted directory pointing into a denied one is
   **not listed**. —
   `test_a_symlink_into_a_denied_directory_is_not_listed`
2. Reading it through `read_permitted` is **refused**, with
   `SourceAccessDeniedError`. —
   `test_reading_through_the_denied_path_is_refused`
3. The walk **does not ingest** it, and no denied text reaches
   `source_texts`. —
   `test_a_symlink_into_a_denied_directory_is_not_ingested`
4. `read` still reads — it is the unchecked primitive, unchanged. —
   `test_read_remains_the_unchecked_primitive`
5. A permitted file is unaffected: listed, readable, ingested. —
   `test_read_permitted_still_reads_what_is_permitted`, plus the listing and
   ingestion assertions in tests 1 and 3
6. A caller of `filter_listing` that passes no resolver sees the previous
   behaviour. —
   `test_a_caller_without_a_resolver_keeps_the_previous_behaviour`

Contracts 1, 2, 4, 5 and 6 are in `tests/test_security_listing_canonical.py`,
in the layer that was wrong. Contract 3 is about ingestion and the store, so
it is in `tests/test_material_walk.py`.

Contracts 1, 2 and 5 are asserted twice: once against a **symlink** and once
against an **NTFS junction**. The Context above says a junction leaked the same
way, so the fix has to be measured on the construct the ADR names rather than
argued from the symlink case — they are different reparse points, and whatever
resolves one is not thereby shown to resolve the other. Both were
mutation-checked: dropping the resolver fails both.

A seventh test, `test_every_ingested_file_passed_through_the_policy_check`,
pins the second check itself. Without it the two layers are not equally
protected: while the listing is correct the denied symlink is never visited,
so reverting the walk to the unchecked `read` keeps the whole suite green
while the layer disappears and this ADR's "does not depend on the first being
right" stops being true. Both layers were mutation-checked — removing the
resolver from `list_dir` fails contract 1, and reverting the walk to `read`
fails only the seventh test.

## Known gaps

Ratification approves the execution of §C5 described above. It does not close
these, which are open as of the merge. The first two were measured against the
tree at `729a84a`, not inferred:

- **`filter_listing`'s resolver is optional, so the unsound path stays
  reachable.** Contract 6 requires that a caller without a resolver keeps the
  old behaviour, which is exactly the declared-spelling-only matching this ADR
  exists to remove. Nothing makes that failure loud: a future caller that
  forgets `resolve` gets a listing that looks filtered and is not. Measured:
  `list_dir` is the only production caller and it passes a resolver, so nothing
  in `src/` is affected today — but that is a property of today's call graph,
  not an enforced one.
- **`read` stays reachable and unchecked, deliberately.** Measured: the only
  caller of `read` in `src/` is `read_permitted` itself, so no production path
  skips the check today, and the tool layer that `read`'s docstring defers to is
  not built yet. The property does not survive a future caller using `read`
  directly, and only its docstring stands in the way. This is the same shape as
  the defect above, accepted knowingly rather than by oversight.
- **The per-entry `Path.resolve` cost is unmeasured.** A listing now pays a
  syscall per entry that it did not pay before. Nobody has run a listing of a
  large workspace; the re-evaluation trigger below names the threshold to
  watch, not a number.
- **Junction coverage is Windows-only.** The junction tests skip on every
  other platform, because NTFS junctions are a Windows facility. The Linux
  runner therefore never exercises that case — correct, since Linux has no
  equivalent construct, but it means the Linux green is not evidence about
  junctions.

## Re-evaluation trigger

Re-open if the per-entry `Path.resolve` cost shows up in a listing of a
large workspace. The alternative is resolving lazily, only for entries a
rule would actually deny — but that inverts the evaluation, and a rule
whose matching depends on what was resolved first is harder to reason about
than one that resolves everything.
