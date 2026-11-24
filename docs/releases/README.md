# Release records

**Every version of LabCairn gets one structured record under
`docs/releases/`, and the record is what the release is.** The prose in
[`../RELEASE-NOTES.md`](../RELEASE-NOTES.md) explains; the record states.

## The seven elements

Phase 4 §10 requires every version to record seven things.  A record
missing any of them is not a release record, and
[`scripts/release_record.py`](../../scripts/release_record.py) refuses to
write one and fails a check on one:

| # | Field | What it holds |
|---|-------|---------------|
| 1 | `version`, `commit` | the version number and the exact source commit it was built from |
| 2 | `artifact_sha256` | the installer artifact's sha256, or an explicit `null` **and** a non-empty `artifact_sha256_reason` |
| 3 | `compatibility` | two columns, `data` and `api`: what data this version reads and writes, and what API it promises |
| 4 | `added` | the new capabilities, as a non-empty list of non-empty strings |
| 5 | `fixed` | the issues this version fixes |
| 6 | `known_limits` | the limits that remain open after this version |
| 7 | `rollback` | how to roll this release back, in one non-empty statement |

Two bookkeeping fields ride along: `branch` (where the release was cut)
and `created_at` (a UTC ISO-8601 timestamp, written by the tool, never
typed by hand).

## File naming

One JSON object per version, named for it: version `0.2.0` lives at
`docs/releases/0.2.0.json`.  The file name is not decoration —
`check` verifies that the record's `version` matches the file name stem,
so a record cannot be renamed past its own content.

## Usage

`create` assembles a record from git, an optional artifact, a notes file
and the command line, and writes it:

```
python scripts/release_record.py create \
  --version 0.2.0 \
  --artifact dist/labcairn-0.2.0.whl \
  --notes docs/releases/0.2.0.notes.yaml
```

The commit, the branch and `created_at` are **measured here, never taken
from the notes**; the artifact is hashed, never copied.  The notes file
may be JSON or YAML and carries the author's statements:
`compatibility` (`data` and `api`), `added`, `fixed`, `known_limits`,
`rollback`, and `artifact_sha256_reason` when no artifact exists.
Command-line flags (`--data-compatibility`, `--api-compatibility`,
`--added`, `--fixed`, `--known-limits`, `--rollback`) win over the notes
file, field by field.

A version number that already has a record is refused unless `--force`
is passed — overwriting a record is a deliberate act, not a side effect.

`check` measures one record and names everything wrong with it, not
just the first problem:

```
python scripts/release_record.py check docs/releases/0.2.0.json
```

It verifies the seven elements, that `commit` is a commit in this
repository's history, that `created_at` is a valid UTC ISO-8601
timestamp, and that `version` matches the file name.  It exits non-zero
when anything fails.

## Measured, not carried forward

A number or digest in a record is **measured at that release**.  The
commit is read from git at write time, the artifact digest is computed
from the artifact's bytes, and `created_at` is written by the tool.  A
value from an older record is never reused for a new one — a record that
carries a previous release's numbers describes a release that does not
exist.

## v0.1.0 — the first runnable Phase 4 version

[`v0.1.0.json`](v0.1.0.json) is the first runnable version's record: it
covers the Phase 4 delivery work merged through the sixth batch (the
closed delivery loop, the multi-source index over paper trajectories,
slide decks and meeting text, rule sharing, the pilot preparation
records and the structured release-record tool itself).  Its version
number and date were **confirmed by the owner on 2026-11-24** and the record
was re-anchored to the post-batch-7 commit.  Plan §12's third decision (the first runnable Phase 4 version and the first
trial date) is confirmed in
[`../plans/LC-P4-PILOT-owner-decisions.md`](../plans/LC-P4-PILOT-owner-decisions.md);
a later rename is a deliberate act and goes through `create --force` on
the new version number, never by editing the file in place.
The record's `artifact_sha256` is an explicit `null` with its reason: no
installer artifact has been built, and the digest must be measured from
real installer bytes, not asserted.
