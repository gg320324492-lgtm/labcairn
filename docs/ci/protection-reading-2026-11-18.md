# The protection reading of 2026-11-18 — seventeen contexts

**What this is.** The record of one change to this repository's account of
GitHub's branch protection: the owner added the two `shard 5` legs the matrix
grew on 2026-11-15, and this repository's reading of the protection was
re-taken afterwards. The reading itself is a file a program can read —
[`required-checks-reading.json`](required-checks-reading.json) — and this
document says what was measured, what it means, how the change was made, and
how the next reader knows it has gone stale.

**Why it is a document and not only a file.** The reading file holds the
numbers. It does not hold the two ways the write that produced them goes
wrong, and both of those ways report success.

## 1. The reading

| | |
|---|---|
| taken at | **2026-11-18T03:48:46Z** |
| taken at the revision | `ac362d2cb5536d05372cf02b49a499036efd2952` (the tip of `origin/main` when it was taken) |
| read with | `gh api repos/gg320324492-lgtm/labcairn/branches/main/protection` |
| `required_status_checks.contexts` | **17** |
| `required_status_checks.checks` | **17**, every one of them bound to app `15368` |
| `strict` | **`true`** |
| `enforce_admins` | `enabled: true` |
| `required_pull_request_reviews` | `null` — the owner decided on 2026-11-11 that no required review is added |

The seventeen names, one per line, are the block in
[`.github/CI.md`](../../.github/CI.md) between the
`required-status-checks` markers, and they are the `required_contexts` list in
the reading file.

## 2. What changed, and what did not

**Changed.** The two `shard 5` legs —
`python-quality (ubuntu-latest, shard 5)` and
`python-quality (windows-latest, shard 5)` — were added to GitHub's required
status checks on 2026-11-18. Before that day the protection required
**fifteen** contexts; it now requires **seventeen**.

**Not changed.** Nothing was lost. The fifteen of 2026-11-11 are all still
there, `strict` is still `true`, `enforce_admins` is still on, and the seven
jobs the tree reports that the protection still does not wait for are the same
seven as before: `evaluation`, `real-model smoke`, `release-contents`, both
`release-dependency-licences (…)` legs and both `shell-test (…)` legs. `shell-test`
and the release jobs stay outside the gate by the owner's decision of
2026-11-11, which is a decision and not a gap.

**The consequence for the shard partition.** `.github/make_ci_shards.py` keeps
every test file in at least one leg the reading names. With every leg named,
that constraint has nothing left to repair and the partition is the plain
balance again. **The next time the matrix grows, it is back**: a leg the
matrix adds and the gate has not caught up with is a leg the reading has to
name, or the witness says so.

## 3. The two ways the write goes wrong, and both of them look like success

The endpoint that reads the protection is not the endpoint that writes it.

1. **The total endpoint does not write.** `PATCH
   /repos/{owner}/{repo}/branches/{branch}/protection` answers **404 Not
   Found**, while a `GET` on the very same path answers normally — so the path
   that reads the setting perfectly looks like a path that has one. A write
   has to go to the sub-resource
   `PATCH /repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks`.
2. **The sub-resource wants the inner body.** The body it takes is
   `{"strict": true, "contexts": [...]}`. The outer wrapper,
   `{"required_status_checks": {...}}`, is answered with **200** and changes
   nothing at all. The write succeeds and the setting is exactly as it was.

So a write that reports success has to be followed by a **re-read**, and the
re-read has to compare two things rather than one: the **count** of the
returned contexts, and the **difference** between the old set and the new one.
A count alone would not have caught the second failure above either, because a
wrapper that changes nothing leaves the count where it was.

The before and after states of this change were kept in the owner's local
workspace under `E:/labcairn-local/`, outside this repository, so that the
difference could be read rather than remembered.

## 4. How to know it has drifted again

Two mechanisms, and neither substitutes for the other.

* **[`required-checks-reading.json`](required-checks-reading.json)** is the
  reading. It holds the instant it was taken, the revision it was taken at,
  the names it returned, every name the workflows in this repository report,
  and the names that are reported and not required. It is rewritten when
  somebody re-reads the protection with credentials — and **it is the only
  place the real protection is visible**, because CI holds no GitHub
  credentials.
* **`tests/test_ci_shard_coverage.py`** watches the tree against that file.
  It checks that every required context is a name a workflow in this
  repository reports, that the required list and the unprotected list together
  are exactly the names the tree reports, that every leg the matrix expands to
  is either required or named in `pending_protection_additions`, that the
  revision the reading names is a commit this checkout still has, that the
  shard count is the matrix's, and that the counts the pointers state are the
  count of the block in `.github/CI.md`. **A leg that is neither required nor
  named in the pending list fails the suite** — that is how the drift of
  2026-11-15 was caught, and it is what catches the next one.

**What neither of them can do.** They cannot see GitHub. A context added to
or removed from the protection on GitHub is invisible to the suite until
somebody re-reads it with credentials and rewrites the reading. That is why
the reading carries the command that re-reads it, and why this document names
the moment it was last taken.

## 5. Re-reading it

```
gh api repos/gg320324492-lgtm/labcairn/branches/main/protection \
  --jq '{contexts: (.required_status_checks.contexts | length),
         strict: .required_status_checks.strict,
         checks: (.required_status_checks.checks | length)}'
# -> {"checks":17,"contexts":17,"strict":true}
```

Then compare the returned names with the block in `.github/CI.md` and with
`required_contexts` in the reading file, and rewrite the reading if they
differ. The reading's `read_at_utc` and `read_at_revision` are what make two
readings comparable; `pending_protection_additions` is what says, in the
record itself, that the matrix has grown past the gate.
