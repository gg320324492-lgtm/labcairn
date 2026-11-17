# The external-path reading — 2026-11-18

**What this is.** The reading of the paths under `E:/labcairn-local` that
this repository's records name, and the ledger that carries the result:
[`external-paths.json`](external-paths.json).

**Why the reading exists.** A pack was renamed on 2026-11-18 and a record
still pointed at the old name. A reader who follows that pointer finds
nothing and falls into the trap the rename was made to close. Renaming a
pack does not update the records that name it, and nothing watched them.
The reading is that watcher.

## 1. The moment of the reading

Two readings, and they are not the same one.

| | what was read | when |
|---|---|---|
| the project reading | every record on three surfaces — the project memory, the repository, and the external packs | **2026-11-18T04:02:23+08:00**, the `scanned_at` the tool wrote into its own inventory |
| the repository ledger | the tracked files of this repository, re-read after the four repairs of §5 | 2026-11-18 |

The project reading's tool, its manifest and its report are under
`E:/labcairn-local/path-liveness-20261118/`; its report is the authority
for §2.1 and this ledger is the authority for §2.2 and for everything
after it.

## 2. What the reading found

### 2.1 The project reading

**26 187 reference sites** name **4 320 distinct paths** across 2 131
files.

| | paths |
|---|---|
| the path resolves now | **1 301** |
| the path does not resolve | **2 957** (62 of them have a rename candidate) |
| — a live record still points at it with nothing to say it is gone | **4** |
| — a live record points at it and the record says so | 352 |
| — no live record points at it any more | 3 964 |

The four in bold were all in this repository, and §5 says what became of
them. The 352 are not defects: the record names a path and says that the
path is not there, which is a different sentence from offering a place
that is not there.

### 2.2 The repository ledger

**222 distinct paths** are named by **88 tracked files**, at **345
reference sites**.

| the ledger's expectation | paths | what it means |
|---|---|---|
| `present` | **144** | the path is on disk, and the record may offer it |
| `absent` | **76** | the path is not on disk and is not expected to be |
| `renamed` | **2** | the path moved; the ledger names where it went |

The 76 `absent` paths are not 76 defects. They fall into kinds, and the
kind says what the record is doing:

| the ledger's kind | paths | what the record is doing |
|---|---|---|
| `material` | 148 in total | the path held something a reader was sent to |
| `scratch` | 40 | a directory a run used and cleaned up |
| `created` | 23 | a path a script creates |
| `pattern` | 8 | the record wrote a shape — a wildcard or a placeholder — not an address |
| `prospective` | 2 | a path a future step will create |
| `historical` | 1 | a path a past run used, with no offer in the sentence |

**Five** of them are `material` and gone — three `absent` and two
`renamed`. Those five are the ones a record has to announce, and they are
the five the witness watches.

## 3. The rule the ledger encodes

> **A rename is not a defect. A bare pointer to the old name is.**

A path that moved is still the material a reader wants, so the record is
repaired by naming the new address beside the old one, dated. A path that
is simply gone is repaired by saying so, dated. What is not allowed is a
record that names a path which is not there **and says nothing about it**:
that is the dangling pointer, and it is what this ledger exists to catch.

So a path's entry in the ledger carries three things: what the path is
expected to be, the kind that says whether the record offers it, and — for
a path that held material and is gone — **the wording the record has to
carry** where it names that path. The witness then checks every reference
site against that wording.

The rule has a second half, and it is the one that keeps the ledger
honest: **every path a tracked file names is in the ledger.** A record
that starts naming a new external path is a path the ledger does not know
about, and the witness says so instead of the ledger quietly going out of
date.

## 4. What runs where

**The repository half runs in CI.** It needs only the tree:

* every path a tracked file names is in the ledger;
* a path the ledger says is gone is never named bare — the paragraph that
  names it carries the wording the ledger requires;
* a renamed path is named together with the path that replaced it, so a
  reader is never left with the old name alone.

**The packs half runs on a development machine.** Whether
`E:/labcairn-local/...` is on disk is a question about a machine, not
about the tree, and a runner has no `E:` pack root at all. So the
existence check is **skipped, not failed**, where the root is absent:

* `present` — the path must be there;
* `renamed` — the replacement must be there and the old name must not be;
* `absent` — the path must not be there.

### The development-machine entry point

```
python scripts/check_external_paths.py
```

| exit code | meaning |
|---|---|
| **0** | every check that could run passed — the repository half, and the packs half if this machine has the packs |
| **2** | at least one check failed: a dangling pointer, a bare reference, a stale ledger entry, or a path that is not where the ledger says it is |
| **1** | the ledger could not be read, or the tree could not be listed |

`--ci-only` runs the repository half alone, which is what a runner does.

The ledger is refreshed with:

```
python scripts/build_external_path_ledger.py            # report the differences
python scripts/build_external_path_ledger.py --write    # write them
```

A refresh re-reads the tree, re-derives the sites, and **keeps the
expectations** — an expectation is a judgement about a path, and a refresh
is not where a judgement is re-made. A path that appears for the first
time is added with what the disk says about it; if it is not there, the
ledger entry arrives with no announcement, and the witness then refuses
the ledger until the record has been fixed and the wording written down.

## 5. The four repairs

Each is a dated supersede: the old reading is kept, and the date says why
it changed. The wording the ledger requires is the wording below.

| the record | the path | what it says now |
|---|---|---|
| `docs/papers/pilot-method.md` | `materials-library\pilot-model-proposal.json` | the library was reorganised into one directory per corpus on 2026-10-31, so the file **moved, not deleted**; the address is now `materials-library\corpus-1-mn-bubbles\pilot-model-proposal.json` |
| `docs/acceptance/LC-P2-08-batch11-version-graph.md` | `batch11-graph\rehearsal.db` | the rehearsal copy **is not on disk** as of 2026-11-18; the digests the write plan records are what survive |
| `docs/acceptance/g5-review-records.md` (two sites) | `harness-final2\evaluation-report.md` | that path **is not on disk** any more; only `harness-final2.log` survives |
| `docs/acceptance/LC-P2-07-table-row-markers.md` | `row-marker-measure\mut\` | the copy **is not on disk** any more; the scripts that made it are still there |

The fifth material path — `rerun12-exec-20261117`, **renamed, not deleted**,
to `_OBSOLETE-transparent-png__rerun12-exec-20261117/` — was already
announced in the records that name it, so it needed no repair; the ledger
carries it because the witness watches it the same way.

**Every one of these was verified against the disk before it was written,
not taken from the reading's report.** The report and the reading agreed
on all five, but the report is a claim and the disk is the measurement.

## 6. What this reading does not say

- **It is not a freshness check.** It says whether a path is there, not
  whether what is inside it is current.
- **It is not a review of the packs.** It says that a record's pointer
  resolves, not that the pack behind it is right.
- **It does not cover the packs' own internal references.** The project
  reading did read them — 25 816 of the 26 187 sites are in the packs —
  but this ledger covers this repository only.
- **It does not run on a runner.** The existence half needs the machine
  the packs are on; §4 says which half is which, and the witness skips
  the other rather than failing it.
