# LC-P1-00 — Acceptance Evidence

**Work order:** LC-P1-00 — External Agent source study and design evidence (P0)
**Gate fed:** G0 — Upstream study setup (`docs/PHASE_1_WORKORDERS.md:138`)
**Evidence date:** 2026-10-15
**Status of the work order:** completed with one item deferred (§2.7) and one item
judged **not met** by this work order (§2.5, partial) — see §4 for the full list of
what this round did *not* establish.

---

## 0. How to read this document

Every claim below is written as **a command an external reviewer can run and an
output they should expect to see**. Nothing here says "verified" on its own.

Three rules govern the wording used throughout:

| Wording | Meaning |
|---|---|
| **PASS** | The command ran, and its actual output is reproduced verbatim below. |
| **PARTIAL / NOT MET** | The command ran and its output does **not** establish the requirement. |
| **NOT APPLICABLE / DEFERRED** | The requirement belongs to a different work order, or cannot be closed by this one. |

**Environment assumed by the commands.** All commands are given for the development
machine (Windows 11, Git Bash, `python` = CPython 3.10) unless stated otherwise.
Commands fall into two classes, and each one is tagged inline:

- **[repo]** — runs inside a clone of the LabCairn repository alone. An external
  contributor who has never cloned an upstream project can run all of these.
- **[upstream]** — runs inside `E:/labcairn-upstreams/<repo>/` and therefore requires
  the reviewer to have cloned the upstream projects themselves. §5 explains what a
  reviewer without those clones can and cannot check.

> **Standing caveat for every `[upstream]` command.** The five study clones were made
> with `git clone --depth 1 --filter=blob:none --single-branch`. The pinned SHAs
> therefore exist **only in the local object store on this machine**. GitHub may
> force-push or garbage-collect any of them, and a fresh `git clone` will almost
> certainly land on a *different* commit. `docs/UPSTREAM_REFERENCES.md:32` and
> `:108` state this; it is repeated here because it bounds the value of every
> upstream line-number citation in §3. A line-number claim such as
> `deepagents/graph.py:893-919` is reproducible **only** by reproducing that exact
> snapshot.

---

## 1. Deliverables inventory and location

The work order names six deliverables (`docs/PHASE_1_WORKORDERS.md:36`):
a local checkout manifest with SHAs (not Git-tracked), a public upstream reference
index, 2+ ADRs prior to G1, 1+ evidence/provenance ADR prior to G3, a documented
licensing/attribution check at G5, and a repository that functions without any
upstream checkout present.

| # | Deliverable (work order wording) | Actual artifact | Tracked by Git? | Verify with |
|---|---|---|---|---|
| D1 | local checkout manifest with SHAs | `E:/labcairn-upstreams/snapshot.json` | **No** — outside the repo, and `labcairn-upstreams/` is in `.gitignore:4` | §1.1 |
| D2 | public upstream reference index | `docs/UPSTREAM_REFERENCES.md` | Yes | §1.2 |
| D3 | 2+ architecture ADRs prior to G1 | `docs/adr/ADR-0002-model-and-tool-execution-boundary.md`, `docs/adr/ADR-0003-event-and-permission-model.md` | Yes | §2.3 |
| D4 | 1+ evidence/provenance ADR prior to G3 | `docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md` | Yes | §2.3 |
| D5 | documented licensing/attribution check | `docs/UPSTREAM_REFERENCES.md:50`–`:83` (§"Verified license boundaries"), incl. the per-subpackage walk | Yes | §3.2 |
| D6 | repository functions without upstream clones | the repository contains 12 files, all docs/config; no package, no CI, no test suite depends on a clone | Yes | §2.5 |

**Local-only, deliberately not in Git:** the five study clones themselves
(`E:/labcairn-upstreams/{pydantic-ai,openhands-sdk,deepagents,paper-qa,paperspine}`,
**701 MB** as re-measured — see §4.3).

### 1.1 The manifest exists, is outside the repository, and its SHAs match the clones [repo + upstream]

```bash
# from the LabCairn repo root
cat /e/labcairn-upstreams/snapshot.json | head -5
```

Expected (this machine; `created_at`/`updated_at` differ per machine and per run):

```
{
  "manifest_version": 1,
  "created_at": "2026-10-15T05:14:50.602836+00:00",
  "updated_at": "2026-10-15T05:15:55.830400+00:00",
  "repos": {
```

> The two timestamps differ by ~65 seconds because the manifest was written twice —
> the study wave, then a targeted follow-up. That difference is itself the primary
> evidence for finding 3.1: a script that rebuilt the manifest from scratch would
> have made `created_at == updated_at` on the second run.

Cross-check every pinned SHA against the live object store [upstream]:

```bash
cd /e/labcairn-upstreams
for r in pydantic-ai openhands-sdk deepagents paper-qa paperspine; do
  printf "%-16s " "$r"; git -C "$r" rev-parse HEAD
done
```

Actual output:

```
pydantic-ai      9ac853bb84ffed7ba0edccb026c5b4f3228c1de7
openhands-sdk    8efff8d3cf1a5a3fcf7ce5e3b97c7f00684d9547
deepagents       825acb3ca03bd103e4df6013b122eca8475d1982
paper-qa         57e89f7223b0960d5ee5ea048c69e3c47e088572
paperspine       42312b8d9c76ab25990cddfd76e3622276854118
```

These five values match the `Commit SHA` column of
`docs/UPSTREAM_REFERENCES.md:36-40` exactly. A reviewer who clones fresh **must
not** expect these SHAs — see the standing caveat in §0.

### 1.2 The public index is tracked and contains no third-party source [repo]

```bash
cd /e/LabCairn
find . -type f -not -path "./.git/*" -not -path "*/__pycache__/*" -not -path "./tmp/*" | sort
```

Actual output — 12 files, all of them first-party:

```
./.gitignore
./README.md
./docs/ARCHITECTURE.md
./docs/EVALUATION.md
./docs/PHASE_1_WORKORDERS.md
./docs/ROADMAP.md
./docs/UPSTREAM_REFERENCES.md
./docs/adr/ADR-0002-model-and-tool-execution-boundary.md
./docs/adr/ADR-0003-event-and-permission-model.md
./docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md
./docs/adr/ADR_TEMPLATE.md
./scripts/checkout_upstreams.py
```

No vendored tree, no submodule, no subtree merge [repo]:

```bash
cd /e/LabCairn; ls .gitmodules; git config --get-regexp submodule
```

Expected: `ls: cannot access '.gitmodules': No such file or directory` and
`git config --get-regexp submodule` produces no output and exits non-zero.

---

## 2. Acceptance items, one by one

The work order's own acceptance sentence is `docs/PHASE_1_WORKORDERS.md:38`:

> **Acceptance:** external repos are not tracked, bundled, dependency-imported, or
> given execution authority; references include immutable commit SHAs and source
> file/section pointers; claims about borrowed behavior are grounded in inspected
> code/tests; architecture decisions include rejected options. Reference clones are a
> **development-only** aid and do not block an external contributor who hasn't
> cloned them.

The operational checklist used below is the eight-item list at
`docs/UPSTREAM_REFERENCES.md:170-179`, which is the closest thing to a per-item
statement of the same acceptance.

### 2.1 Reference clones are located outside tracked source

**Requirement (`UPSTREAM_REFERENCES.md:172`):** "References are outside tracked
LabCairn source, or ignored and independently verified as untracked."

**Evidence [repo].** Three separate mechanisms, each independently checkable:

(a) *Physical separation* — the clones are not in the repository at all; §1.2's
inventory shows 12 files and none is third-party source.

(b) *Ignore rules match* — `git check-ignore -v` resolves each of the three
documented globs to its `.gitignore` line:

```bash
cd /e/LabCairn
for p in _references/x .upstreams/x labcairn-upstreams/x; do
  printf "%-24s " "$p"; git check-ignore -v "$p" || echo "NOT IGNORED"
done
```

Actual output:

```
_references/x          .gitignore:2:_references/	_references/x
.upstreams/x           .gitignore:3:.upstreams/	.upstreams/x
labcairn-upstreams/x   .gitignore:4:labcairn-upstreams/	labcairn-upstreams/x
```

(c) *Not tracked* — `git ls-files` returns nothing reference-shaped. **Caveat on this
command:** at the time of writing the repository has **no commit yet**, so
`git ls-files` is empty *by construction* and proves nothing on its own. After the
initial commit the meaningful form of this check is:

```bash
cd /e/LabCairn
git ls-files | grep -iE "reference|upstream" ; echo "matches above (none expected)"
```

**Verdict: PASS.** Separation is real and enforced three ways. But note honestly
that this verifies *ignore rules*, not *packaging* — packaging does not exist yet
(§2.5, §3.5).

### 2.2 Reference projects carry a pinned SHA, a license and a reason for examination

**Requirement (`UPSTREAM_REFERENCES.md:173-174`):** "Chosen projects have a recorded
exact commit SHA, license and reason for examination"; subdirectory licenses walked,
not just root licenses.

**Evidence [repo]** — for each of the five cloned projects, `docs/UPSTREAM_REFERENCES.md:34-40`
records all three fields:

| Field | Where | Sample (`paper-qa`) |
|---|---|---|
| Canonical URL | table col. `GitHub` | `https://github.com/Future-House/paper-qa` |
| Inspected commit SHA | table col. `Commit SHA` | `57e89f7223b0960d5ee5ea048c69e3c47e088572` |
| License at that revision | table col. `Root license (verified)` | `Apache-2.0 at root, **AGPL-3.0 in packages/paper-qa-pymupdf/**` |
| Subject area / reason | table col. `Study areas` | `scientific retrieval, excerpts, citation/provenance` |
| Inspected source paths | §3 of this document + each ADR's "Upstream evidence" section | — |

Check that every SHA cited in the ADRs is one of the five pinned SHAs [repo]:

```bash
cd /e/LabCairn/docs/adr && grep -ohE "\b[0-9a-f]{40}\b" *.md | sort -u
```

Actual output — five SHAs, no strays:

```
42312b8d9c76ab25990cddfd76e3622276854118
57e89f7223b0960d5ee5ea048c69e3c47e088572
825acb3ca03bd103e4df6013b122eca8475d1982
8efff8d3cf1a5a3fcf7ce5e3b97c7f00684d9547
9ac853bb84ffed7ba0edccb026c5b4f3228c1de7
```

The four `not cloned` projects (`opencode`, `gpt-researcher`, `storm`,
`ai-scientist-v2`) deliberately carry **no SHA** — `UPSTREAM_REFERENCES.md:46` states
that an invented or guessed SHA "is worse than a blank, because it looks verifiable."
That is the correct call and is recorded here as evidence of intent, not as a gap.

The licenses were opened at the pinned SHA rather than read off GitHub metadata —
`UPSTREAM_REFERENCES.md:30` says so explicitly and §3.2 demonstrates one case.

**Verdict: PASS.**

### 2.3 Two architecture ADRs before G1, one provenance ADR before G3

**Requirement (`PHASE_1_WORKORDERS.md:34,36`; `UPSTREAM_REFERENCES.md:175`):** "at
least 2 concise architecture ADRs precede G1; at least 1 provenance/evidence ADR
precedes G3." The gate table at `PHASE_1_WORKORDERS.md:139` requires ">=2
architecture comparison ADRs" at G1 and an "evidence design ADR" at G3.

**Evidence [repo].**

```bash
cd /e/LabCairn/docs/adr && grep -n "^#\{1,2\} " ADR-000{2,3,4}-*.md
```

Actual output:

```
=== ADR-0002-model-and-tool-execution-boundary.md
1:# ADR-0002: Model and tool execution boundary
7:## Context and concrete problem
29:## Alternatives, including simpler/no-dependency option
59:## Upstream evidence (reference only)
193:## Decision and why this fits LabCairn
377:## Risks, tradeoffs and reversibility
391:## Contracts and acceptance tests
432:## Re-evaluation trigger
=== ADR-0003-event-and-permission-model.md
1:# ADR-0003: Event model and permission model
7:## Context and concrete problem
26:## Alternatives, including simpler/no-dependency option
139:## Upstream evidence (reference only)
274:## Decision and why this fits LabCairn
288:## Risks, tradeoffs and reversibility
306:## Contracts and acceptance tests
487:## Re-evaluation trigger
=== ADR-0004-scientific-provenance-and-evidence-model.md
1:# ADR-0004: Scientific provenance and evidence model
7:## Context and concrete problem
26:## Alternatives, including simpler/no-dependency option
56:## Upstream evidence (reference only)
125:## Decision and why this fits LabCairn
137:## Risks, tradeoffs and reversibility
151:## Contracts and acceptance tests
279:## Re-evaluation trigger
290:## Safety note on upstream material
```

| Gate requirement | Satisfied by | Work orders it feeds |
|---|---|---|
| 2 architecture comparison ADRs before G1 | ADR-0002 (model/tool execution boundary) + ADR-0003 (event/permission model) | LC-P1-02/03 and LC-P1-04/05/06 |
| 1 evidence/provenance ADR before G3 | ADR-0004 (scientific provenance and evidence model) | LC-P1-09; input for LC-P1-08; prerequisite for G3 |

"Architecture decisions include rejected options" is checkable: each ADR has an
explicit "Alternatives, including simpler/no-dependency option" section followed by
a decision section [repo]:

```bash
cd /e/LabCairn/docs/adr && for f in ADR-000[234]-*.md; do
  printf "%-50s reject-mentions=%s\n" "$f" "$(grep -ci reject "$f")"
done
```

Actual output:

```
ADR-0002-model-and-tool-execution-boundary.md     reject-mentions=15
ADR-0003-event-and-permission-model.md            reject-mentions=29
ADR-0004-scientific-provenance-and-evidence-model.md reject-mentions=11
```

**Caveat on "concise":** the work order asks for *short* ADRs; these three total
162,817 bytes across 1,233 lines (445 / 496 / 292), and the longest runs to 496
lines. They follow the required template (problem → alternatives → inspected source
@ SHA → choose/reject → local contract → test) but they are long. Whether that
satisfies "concise" is a judgement call this document does not make on the author's
behalf; a reviewer may disagree.

**Verdict: PASS on count and structure; "concise" is contested.**

### 2.4 Upstream instructions are not treated as trusted commands

**Requirement (`UPSTREAM_REFERENCES.md:176`):** "Upstream instructions are not treated
as trusted commands or executable requirements."

**Evidence — the exposure is measured, not assumed [upstream].** The count of
agent-instruction files across the five clones:

```bash
cd /e/labcairn-upstreams
for r in pydantic-ai openhands-sdk deepagents paper-qa paperspine; do
  a=$(find "$r" -name AGENTS.md   -not -path "*/.git/*" | wc -l)
  c=$(find "$r" -name CLAUDE.md   -not -path "*/.git/*" | wc -l)
  s=$(find "$r" -name SKILL.md    -not -path "*/.git/*" | wc -l)
  echo "$r  AGENTS.md=$a  CLAUDE.md=$c  SKILL.md=$s  TOTAL=$((a+c+s))"
done
find . -name AGENTS.md -o -name CLAUDE.md -o -name SKILL.md | grep -v "/.git/" | wc -l
```

Actual output:

```
pydantic-ai  AGENTS.md=21  CLAUDE.md=16  SKILL.md=22  TOTAL=59
openhands-sdk  AGENTS.md=8  CLAUDE.md=0  SKILL.md=21  TOTAL=29
deepagents  AGENTS.md=17  CLAUDE.md=0  SKILL.md=26  TOTAL=43
paper-qa  AGENTS.md=0  CLAUDE.md=0  SKILL.md=0  TOTAL=0
paperspine  AGENTS.md=0  CLAUDE.md=1  SKILL.md=7  TOTAL=8
139
```

**139 total**, matching `UPSTREAM_REFERENCES.md:138` exactly. See §3.4 for why this
number matters.

**Evidence — the sharpest instance is real [upstream].** `paperspine`'s four
highest-risk artefacts sit at the top level of the tree, next to the study material:

```bash
ls /e/labcairn-upstreams/paperspine | head -12
```

Actual output (note `CLAUDE.md`, `INSTALL.md`, `install.ps1`, `install.sh`):

```
CLAUDE.md
INSTALL.md
LICENSE
README.de.md
...
install.ps1
install.sh
paperspine5
```

**Evidence — the checkout helper gives upstream no execution authority [repo].** It
never runs an upstream script, and it refuses a destination inside the tracked tree:

```bash
cd /e/LabCairn
python scripts/checkout_upstreams.py --repo pydantic-ai --dest E:/LabCairn/tmp/references; echo "exit=$?"
```

Actual output:

```
checkout_upstreams.py: error: reference checkout destination must be outside the LabCairn repository
exit=2
```

**Verdict: PASS, with the honest caveat in §4.1.** The *policy* is written down and
the helper enforces the mechanical parts. What is **not** enforced is the part that
actually matters — nothing prevents a future agent or contributor from opening
`paperspine/CLAUDE.md` and obeying it. That control is the LC-P1-01 exclusion
checklist plus human review, and it is **not yet executable** (§3.5).

### 2.5 No hard runtime or CI dependency on reference clones

**Requirement (`UPSTREAM_REFERENCES.md:177`; `PHASE_1_WORKORDERS.md:38`):** "No hard
runtime/CI dependency on reference clones; external contributor can build without
them"; "do not block an external contributor who hasn't cloned them."

**Evidence [repo].** The entire Python surface of the repository is one
stdlib-only helper script:

```bash
cd /e/LabCairn && grep -nE "^(import|from) " scripts/checkout_upstreams.py
```

Actual output — no third-party module anywhere:

```
3:from __future__ import annotations
5:import argparse
6:import json
7:import subprocess
8:from datetime import datetime, timezone
9:from pathlib import Path
```

And the reference paths appear in executable code in exactly one place — a
**default value** for an optional developer flag, never an import path:

```bash
cd /e/LabCairn
grep -rn "labcairn-upstreams\|_references\|\.upstreams" -l . | grep -v "^./docs/" | grep -v "^./.git/"
```

Actual output:

```
./.gitignore
./scripts/checkout_upstreams.py
./scripts/__pycache__/checkout_upstreams.cpython-310.pyc
```

**Evidence — the repo is buildable-but-empty, not broken [repo].** There is no
package, no CI and no test suite yet, so "an external contributor can build it"
is currently vacuous rather than demonstrated:

```bash
cd /e/LabCairn
ls pyproject.toml .github tests src 2>&1
```

Actual output:

```
ls: cannot access 'pyproject.toml': No such file or directory
ls: cannot access '.github': No such file or directory
ls: cannot access 'tests': No such file or directory
ls: cannot access 'src': No such file or directory
```

**Verdict: PARTIAL.** The negative claim — *no dependency on the clones exists* — is
correctly verified and verifiable by any reviewer from the repo alone. The positive
claim — *an external contributor can build without them* — **cannot be tested at
all**, because there is nothing to build. It becomes testable at LC-P1-01. This
document records it as unmet rather than quietly counting the absence of a problem
as the presence of a guarantee.

### 2.6 Copied or adapted source has a per-file license review

**Requirement (`UPSTREAM_REFERENCES.md:178`):** "Any copied/adapted source has a
per-file license/notice review; custom-license material is not copied by default."

**Evidence [upstream].** LICENSE files were enumerated per clone, not read off a
repository-level badge:

```bash
cd /e/labcairn-upstreams
for r in pydantic-ai openhands-sdk deepagents paper-qa paperspine; do
  printf "%-16s %s\n" "$r" "$(find $r -iname 'LICENSE*' -not -path '*/.git/*' -type f | wc -l)"
done
```

Actual output — 31 LICENSE files in total, matching `UPSTREAM_REFERENCES.md:56-60`
file-for-file:

```
pydantic-ai      8
openhands-sdk    3
deepagents      14
paper-qa         5
paperspine       1
```

The decisive finding is in §3.2: the walk found an AGPL-3.0 boundary that a
root-level license check would have missed entirely.

**Verdict: PASS for the *research* phase; formally N/A for the *reuse* clause.**
No upstream source has been copied into LabCairn — §1.2's inventory proves that —
so the per-file notice obligation has not yet been triggered. The obligation is
pre-registered rather than discharged: `UPSTREAM_REFERENCES.md:71` states that
`paper-qa-pymupdf` is "study-only ... unless a deliberate license decision is
recorded", and `:44` marks AI Scientist v2 "no copying by default". The G5
attribution check (`PHASE_1_WORKORDERS.md:36`) is where this becomes a real
obligation; §4.2 records that it has not been performed.

### 2.7 P1 review dossier — **DEFERRED, not done**

**Requirement (`UPSTREAM_REFERENCES.md:179`):** "P1 review dossier names relevant
upstream designs and clearly identifies LabCairn's independent implementation and
its tests."

**Verdict: NOT MET / NOT APPLICABLE TO LC-P1-00.** The checklist item is checked
`- [ ]` (unchecked) at `UPSTREAM_REFERENCES.md:179`, and it is left unchecked. The
reason is structural, not an omission in the record: a *review dossier* is an
end-of-phase artifact. It cannot be written at LC-P1-00 because at LC-P1-00 there is
no LabCairn implementation and no LabCairn test to distinguish from upstream. The
"independent implementation and **its tests**" half of the requirement is
unwritable until LC-P1-02 through LC-P1-13 exist.

This item belongs to **LC-P1-14** (the G5 row, "outsider fresh install, 3 fixtures,
fault injection, docs and real-provider smoke", `PHASE_1_WORKORDERS.md:143`). It is
carried forward, not passed.

---

## 3. Key findings

These are the substantive outputs of the study. Each has a command and its real
output.

### 3.1 `scripts/checkout_upstreams.py` silently erased earlier SHA records

**The defect.** The study workflow is explicitly batched — `UPSTREAM_REFERENCES.md:88`
says "Start with" the must-study clones, `:97` says "Add as needed" `opencode`, and
the helper's own docstring says "Study clones arrive in batches (`--group essential`,
then `--repo opencode`)". The pre-fix script began every run from an **empty**
`records` dict and rewrote the whole manifest. So the second, narrower run of the
documented workflow **dropped the five SHA records written by the first run** — and
did so silently, with a cheerful `Local snapshot written: ...` on stdout. That is
the worst possible failure mode for this project: the evidence file that exists to
pin what was inspected got quietly truncated, and the only record of the loss was
the absence of data.

**Post-fix behaviour** (the code as it stands at
`scripts/checkout_upstreams.py:34-55,79-122`): merge into the existing manifest,
preserve the original `created_at`, add `updated_at` per manifest and `recorded_at`
per record, and refuse to overwrite a snapshot that is corrupt or declares a foreign
`manifest_version`.

#### Reproduction — the fixed behaviour (no network, no upstream code executed)

The trick is that `--dest` can point anywhere outside the repo, and a directory that
already exists is assumed to be a study clone and is *reused, not re-cloned*
(`checkout_upstreams.py:87-95`). So an empty `git init` repository with one commit
is a perfect stand-in: `git rev-parse HEAD` succeeds, no network is touched.

```bash
# 1. Build two stand-in "clones" in a scratch directory OUTSIDE the repo.
mkdir -p /e/tmp/lc-p1-00-repro/dest-fixed
for r in pydantic-ai openhands-sdk; do
  mkdir -p "/e/tmp/lc-p1-00-repro/dest-fixed/$r"
  git -C "/e/tmp/lc-p1-00-repro/dest-fixed/$r" init -q
  git -C "/e/tmp/lc-p1-00-repro/dest-fixed/$r" \
      -c user.name=repro -c user.email=repro@example.invalid \
      commit -q --allow-empty -m "stand-in for a study clone"
done

# 2. Study wave, then the targeted follow-up — the documented batch pattern.
cd /e/LabCairn
python scripts/checkout_upstreams.py --repo pydantic-ai --repo openhands-sdk \
    --dest /e/tmp/lc-p1-00-repro/dest-fixed
python scripts/checkout_upstreams.py --repo pydantic-ai \
    --dest /e/tmp/lc-p1-00-repro/dest-fixed

# 3. Did the unselected record survive?
python -c "import json;d=json.load(open(r'E:\tmp\lc-p1-00-repro\dest-fixed\snapshot.json'));print('repos:',sorted(d['repos']))"
```

Actual output — run 1:

```
Keeping existing checkout E:\tmp\lc-p1-00-repro\dest-fixed\openhands-sdk unchanged
  openhands-sdk: e3d84f2293b90932e45575d4405cdc85edb1f5b7
Keeping existing checkout E:\tmp\lc-p1-00-repro\dest-fixed\pydantic-ai unchanged
  pydantic-ai: e3d84f2293b90932e45575d4405cdc85edb1f5b7
Local snapshot written: E:\tmp\lc-p1-00-repro\dest-fixed\snapshot.json
```

Actual output — run 2 (the narrow one that used to destroy the record):

```
Keeping existing checkout E:\tmp\lc-p1-00-repro\dest-fixed\pydantic-ai unchanged
  pydantic-ai: e3d84f2293b90932e45575d4405cdc85edb1f5b7
Local snapshot written: E:\tmp\lc-p1-00-repro\dest-fixed\snapshot.json
Preserved earlier entries not selected this run: openhands-sdk
```

Actual output — step 3:

```
repos: ['openhands-sdk', 'pydantic-ai']
```

**`openhands-sdk` survived a run that did not select it.** The third line
(`Preserved earlier entries not selected this run:`) is emitted only when merging
worked, so it is a single-token verdict.

#### Reproduction — the pre-fix behaviour

> **Provenance of this reproduction, stated plainly.** The pre-fix source of
> `checkout_upstreams.py` **cannot be recovered from this repository** — LC-P1-00
> closed before the repository had any commit, so no git history preserves the old
> file, and the stale `__pycache__` entry matches the *current* source (its embedded
> size/mtime header equals the on-disk script's). What is reproduced below is a
> faithful re-implementation of the mechanism the fixed file's own docstring names,
> not a recovered artifact. A reviewer who wants the original diff must obtain it
> from the author.

```python
# pre_fix_logic.py -- the pre-fix manifest write, in isolation.
# Unchanged behaviour: start from an empty dict, rewrite the whole manifest.
records: dict = {}
for key in sorted(args.repo):
    sha = subprocess.check_output(
        ["git", "-C", str(dest / key), "rev-parse", "HEAD"], text=True).strip()
    records[key] = {"path": str(dest / key), "commit": sha}
out.write_text(json.dumps(
    {"manifest_version": 1, "created_at": now_iso(), "repos": records}, indent=2))
```

Run it twice against the same pair of stand-ins, second time narrow:

```bash
python pre_fix_logic.py --repo openhands-sdk --repo pydantic-ai --dest .../dest-old
python pre_fix_logic.py --repo openhands-sdk                   --dest .../dest-old
python -c "import json;d=json.load(open(r'...\dest-old\snapshot.json'));print('repos:',sorted(d['repos']))"
```

Actual output:

```
########## PRE-FIX RUN 1 (study wave: both repos) ##########
  openhands-sdk: e3d84f2293b90932e45575d4405cdc85edb1f5b7
  pydantic-ai: e3d84f2293b90932e45575d4405cdc85edb1f5b7
Local snapshot written: E:\tmp\lc-p1-00-repro\dest-old\snapshot.json

########## PRE-FIX RUN 2 (targeted: --repo openhands-sdk only) ##########
  openhands-sdk: e3d84f2293b90932e45575d4405cdc85edb1f5b7
Local snapshot written: E:\tmp\lc-p1-00-repro\dest-old\snapshot.json

########## RESULTING MANIFEST KEYS (pydantic-ai LOST) ##########
repos: ['openhands-sdk']
```

**`pydantic-ai` is gone, and the run that deleted it reported success.** Scale this
to the real workflow: `--group essential` records 5 SHAs, `--repo opencode` erases
5 of them.

#### The corruption guard, also verified

A corrupt or foreign-versioned snapshot is now refused rather than silently replaced
(`checkout_upstreams.py:46-54`):

```bash
cd /e/LabCairn
printf '{"repos": {"pydantic-ai": {"commit": "deadbeef' > /e/tmp/lc-p1-00-repro/dest-fixed/snapshot.json
python scripts/checkout_upstreams.py --repo pydantic-ai --dest /e/tmp/lc-p1-00-repro/dest-fixed; echo "exit=$?"

printf '{"manifest_version": 99, "repos": {}}' > /e/tmp/lc-p1-00-repro/dest-fixed/snapshot.json
python scripts/checkout_upstreams.py --repo pydantic-ai --dest /e/tmp/lc-p1-00-repro/dest-fixed; echo "exit=$?"
```

Actual output:

```
ERROR: E:\tmp\lc-p1-00-repro\dest-fixed\snapshot.json exists but cannot be parsed
(Invalid control character at: line 1 column 47 (char 46)). Move it aside; do not delete it.
exit=1
---
ERROR: E:\tmp\lc-p1-00-repro\dest-fixed\snapshot.json declares manifest_version 99
but this script writes 1. Refusing to overwrite; move it aside or migrate it first.
exit=1
```

In both cases the file on disk was left byte-identical to the input. Note the
behaviour this buys: **losing a pinned commit is now loud**, and the remediation is
"move it aside", never "delete it".

**Independent corroboration from the real run.** Before any of this, the production
`E:/labcairn-upstreams/snapshot.json` was already written twice and shows it:
`created_at` is `05:14:50.602836` while `updated_at` is `05:15:55.830400`
(§1.1). The fixed script is what produced that pair.

### 3.2 `paper-qa` is **not** Apache-2.0

`GitHub` shows `paper-qa` as Apache-2.0. The root is Apache-2.0. **Three of four
subpackages are Apache-2.0. The fourth is not.**

```bash
cd /e/labcairn-upstreams/paper-qa
for d in packages/*/; do n=$(basename "$d")
  if [ -f "$d/LICENSE" ]; then
    printf "%-20s %s\n" "$n" "$(grep -m1 -iE 'GNU AFFERO|Apache License|MIT License|GNU GENERAL' "$d/LICENSE")"
  else printf "%-20s %s\n" "$n" "<no LICENSE file>"; fi
done
printf "%-20s %s\n" "<root>" "$(grep -m1 -iE 'GNU AFFERO|Apache License|MIT License' LICENSE)"
```

Actual output:

```
paper-qa-docling      Apache License
paper-qa-nemotron     Apache License
paper-qa-pymupdf      GNU AFFERO GENERAL PUBLIC LICENSE
paper-qa-pypdf        Apache License
<root>                Apache License
```

It is not a stray file, and it is load-bearing [upstream]:

```bash
cd /e/labcairn-upstreams/paper-qa
grep -n "license" packages/paper-qa-pymupdf/pyproject.toml
grep -n -i "pymupdf" packages/paper-qa-pymupdf/pyproject.toml | head -2
grep -n -m2 "GNU AFFERO\|Version 3" packages/paper-qa-pymupdf/LICENSE
```

Actual output:

```
26:license = {file = "LICENSE"}
21:    "PyMuPDF>=1.24.12",  # For pymupdf.set_messages addition
1:                    GNU AFFERO GENERAL PUBLIC LICENSE
2:                       Version 3, 19 November 2007
```

**Why this matters beyond curiosity.** AGPL-3.0 is the strongest copyleft in common
use: linking it as a library obliges you to offer complete corresponding source of
the combined work to network users. So "PaperQA2 is Apache-2.0" is not merely
incomplete — it becomes **false** at the exact moment someone uses it to justify
adapting `paper-qa-pymupdf`. The obligation is recorded at
`UPSTREAM_REFERENCES.md:70-72`: study-only for LabCairn unless a deliberate license
decision is recorded, and "do not let the AGPL subpackage contaminate the otherwise
permissive analysis of the rest."

The generalizable lesson, stated at `UPSTREAM_REFERENCES.md:52`: **a repository-level
license badge is a root-directory statement, and a root statement is not a repository
statement.**

### 3.3 deepagents advertises planning; its code does not ship it

The catalog originally listed `planning` as a deepagents study area because the
project's own prose says so. At the pinned SHA that is false.

**The claim** [upstream]:

```bash
cd /e/labcairn-upstreams/deepagents/libs/deepagents/deepagents
sed -n '1,6p' graph.py
```

Actual output:

```
"""Primary graph assembly module for Deep Agents.

Provides [`create_deep_agent`][deepagents.graph.create_deep_agent], the main entry
point for constructing a fully configured deep agent with planning, filesystem,
subagent, and summarization middleware.
"""
```

**The shipped code** — the default middleware stack assembled at `graph.py:893-918`:

```bash
sed -n '892,918p' graph.py
```

Actual output:

```
    # Build main agent middleware stack
    deepagent_middleware: list[AgentMiddleware[Any, Any, Any]] = [
        FilesystemMiddleware(
            backend=backend,
            custom_tool_descriptions=_profile.tool_description_overrides,
            _permissions=permissions,
        )
    ]
    sub_agent_middleware: SubAgentMiddleware | None = None
    if inline_subagents:
        sub_agent_middleware = SubAgentMiddleware(
            backend=backend,
            subagents=inline_subagents,
            task_description=_profile.tool_description_overrides.get("task"),
            state_schema=state_schema,
        )
        deepagent_middleware.append(sub_agent_middleware)
    deepagent_middleware.extend(
        [
            create_summarization_middleware(model, backend),
            PatchToolCallsMiddleware(),
        ]
    )
```

`FilesystemMiddleware` → optional `SubAgentMiddleware` → summarization →
`PatchToolCallsMiddleware`. **No planning middleware, no todo middleware.**

Three corroborations, run one at a time so each output is unambiguous [upstream]:

```bash
cd /e/labcairn-upstreams/deepagents/libs/deepagents/deepagents
grep -n "^def create_deep_agent" graph.py
```

Actual output — the entry point, with no `planning` parameter anywhere in it:

```
277:def create_deep_agent(  # noqa: C901, PLR0912, PLR0915  # Complex graph assembly logic with many conditional branches
```

```bash
grep -n "planning" graph.py; grep -c planning graph.py
```

Actual output — the **only** occurrence of the string `planning` anywhere in the
1,015-line file is in the docstring:

```
4:point for constructing a fully configured deep agent with planning, filesystem,
1
```

The claim exists; the parameter and the implementation do not. Next:

```bash
grep -rn "def write_todos" .
```

Actual output — **nothing** (exit status 1). `write_todos` is not defined in this
repository at all. It is LangChain's `TodoListMiddleware`, and outside the test
suite the only place that class appears is the opt-in profile:

```bash
grep -rn "TodoListMiddleware" --include=*.py . | grep -v /tests/
```

Actual output:

```
./profiles/harness/_openai_codex.py:19:from langchain.agents.middleware import TodoListMiddleware
./profiles/harness/_openai_codex.py:72:    Includes `TodoListMiddleware` (the `write_todos` tool) since the Codex
./profiles/harness/_openai_codex.py:77:    middleware: list[AgentMiddleware[Any, Any, Any]] = [TodoListMiddleware()]
```

And the removal is a recorded breaking change, not an accident
(`libs/deepagents/CHANGELOG.md:221`):

```bash
cd /e/labcairn-upstreams/deepagents
sed -n '221p' libs/deepagents/CHANGELOG.md
```

Actual output (truncated at the commit link for width):

```
* `create_deep_agent` no longer includes `TodoListMiddleware` by default, the `write_todos` tool, `todos` state channel, and todo-planning prompt are now absent. ... ([9340518](https://github.com/langchain-ai/deepagents/commit/9340518a26c4287f9ad0c543edc9b69106c15154))
```

So commit `9340518` **deliberately removed** it in v0.7.0, the repo's own test suite
asserts its absence (`tests/unit_tests/test_graph.py:2909`), and the docstring has
never been corrected. The catalog correction is recorded at
`UPSTREAM_REFERENCES.md:48`.

**The rule adopted, which outlasts this finding** — stated at `UPSTREAM_REFERENCES.md:48`:

> a README, docstring or architecture overview is a claim, not evidence — a
> capability counts only when a code path constructs it.

This is the clearest vindication of the project's whole premise: the documentation
asserted a capability for years, and the code never had it.

### 3.4 The prompt-injection surface is a corpus, not a nuisance

**139 agent-instruction files** across five clones (per-repo counts in §2.4;
total verified by an independent count returning `139`).

The distribution is the finding. `SKILL.md` is **an entire file format whose purpose
is to instruct an agent**, and three of the five repos ship 21–26 of them each. The
exposure is not one file per repository; it is a corpus large enough that "remember
that `AGENTS.md` files exist" is not a control. Recorded at
`UPSTREAM_REFERENCES.md:138` as needing exclusion **by name, by directory and by
ingestion root**.

`paperspine` is the sharpest instance: `CLAUDE.md` and `INSTALL.md` sit at the top
level beside `install.sh` and `install.ps1` (§2.4), so the four highest-risk
artefacts are the four most conveniently reachable files in the tree.

**This is a hazard that was *not* triggered.** No upstream code was executed, no
`SKILL.md` body was copied into LabCairn, and no installer was run during LC-P1-00.
The correct reading of the number is "this is what would be exposed", not "this was
exposed".

### 3.5 Reference isolation is promised in prose and **not yet executable**

This is the most important negative finding in the document, so it is stated plainly
rather than buried:

```bash
cd /e/LabCairn
ls tests/test_no_reference_leakage.py pyproject.toml .github/workflows 2>&1
```

Actual output:

```
ls: cannot access 'tests/test_no_reference_leakage.py': No such file or directory
ls: cannot access 'pyproject.toml': No such file or directory
ls: cannot access '.github/workflows': No such file or directory
```

`UPSTREAM_REFERENCES.md:148` already says this in its own words — "The exclusion
promise stated above is currently **unenforceable slogan**" — and this document
corroborates it rather than restating it. Of the three promises, exactly two are in
force today:

| Promise | Status today | Enforced by |
|---|---|---|
| clones live outside the repository | **IN FORCE** | physical separation (§2.1) |
| Git ignores the three reference paths | **IN FORCE** | `.gitignore:2-4`, verified by `check-ignore` (§2.1) |
| not packaged | **ASSERTED ONLY** | nothing — no `pyproject.toml` exists |
| not indexed / ingested | **ASSERTED ONLY** | nothing — no IDE or indexer config exists |
| secret scan covers tracked files only | **ASSERTED ONLY** | nothing — no scan config exists |

**LC-P1-01 inherits this.** The exclusion requirements are already written down as
a testable checklist, so LC-P1-01 has a specification rather than a blank page. Its
source of truth is `docs/UPSTREAM_REFERENCES.md:146-161`, the section
**`## Binding exclusion checklist (applies from LC-P1-01)`**, which specifies the
reference globs (`_references*`, `.upstreams*`, `labcairn-upstreams*`) and, per
target file: explicit `["src/labcairn"]` packaging with auto-discovery disabled;
`MANIFEST.in` prunes; CI `paths-ignore` plus the same exclusion on every
`upload-artifact` and `cache` `path:`; a dedicated CI job asserting `git ls-files` is
clean; `tests/test_no_reference_leakage.py` asserting the same for `git ls-files`
**and** the member names of the built sdist and wheel; git-mode secret scanning (never
`--no-git`); IDE `search.exclude`/`files.exclude` with indexer ingestion root
restricted to `src/` and `docs/`; and `git archive`-only release archiving.

Two limits in that section are **not closable by configuration** and are recorded at
`UPSTREAM_REFERENCES.md:163-168` so they are not re-discovered as false confidence:

1. **The sibling directory is unprotected — highest severity.** `.gitignore` governs
   only its own directory and below, so it says nothing about `../labcairn-upstreams/`.
   A `git init` at `E:/` — or a mistaken `git init ..` from the LabCairn root — makes
   the clones tracked content immediately. No in-repository configuration can prevent
   this; it is an operating-procedure problem assigned to LC-P1-01.
2. **`.gitignore` is weaker than it looks.** It suppresses untracked paths only, so
   `git add -f` bypasses it by design, and pattern matching is case-sensitive on a
   case-sensitive runner.

**One discrepancy found while checking limit 2 on this machine**, reported rather
than smoothed over. With the local `git config core.ignorecase=true`, the case
variants *do* match here:

```bash
cd /e/LabCairn; git config --get core.ignorecase
for p in LabCairn-Upstreams/x LABCAIRN-UPSTREAMS/x; do
  printf "%-24s " "$p"; git check-ignore -v "$p" || echo "NOT IGNORED"
done
```

Actual output:

```
true
LabCairn-Upstreams/x    .gitignore:4:labcairn-upstreams/	LabCairn-Upstreams/x
LABCAIRN-UPSTREAMS/x     .gitignore:4:labcairn-upstreams/	LABCAIRN-UPSTREAMS/x
```

This **does not contradict** the documented limit — it confirms that the limit is a
property of the runner, not of the rule. The behaviour observed here is caused by
this machine's `core.ignorecase=true`; the claim that a case-*sensitive* Linux CI
runner would not match is **untested in this round** and is flagged in §4.2.

---

## 4. What this round did **not** establish

Stated without softening. The project's own rule is that evidence is not truth, only
marked uncertainty.

### 4.1 No upstream code was executed — and no control prevents it from being

LC-P1-00 executed no upstream install script, no test suite, no entrypoint, and no
`pip install`. That is a **behavioural fact about this round**, not an enforced
policy: nothing in the repository mechanically stops a future agent from running
`paperspine/install.sh`. The controls that would actually close this — the ingestion
root restriction and the LC-P1-01 exclusion checklist — **do not exist yet** (§3.5).
Until they do, "we did not execute upstream code" is a claim about the past, not a
guarantee about the future.

### 4.2 Items explicitly recorded as unverified

| Item | Status | Where |
|---|---|---|
| The five pinned SHAs on GitHub | **Unverified, and unverifiable from here.** They exist only in this machine's shallow object store; a fresh clone will not reproduce them. | `UPSTREAM_REFERENCES.md:32,108` |
| Case-sensitive ignore behaviour on a Linux CI runner | **Unverified.** Observed only under this machine's `core.ignorecase=true` (§3.5). | `UPSTREAM_REFERENCES.md:168` |
| The `git init` incident scenario for `E:/` | **Unverified — deliberately so.** Not reproduced, because reproducing it would mean creating exactly the condition being warned about. | `UPSTREAM_REFERENCES.md:167` |
| Current PyMuPDF licensing terms | **Unverified.** The subpackage's dependency declaration is evidence of a constraint, not a reading of PyMuPDF's own license. | `UPSTREAM_REFERENCES.md:73` |
| The license labels as a legal assessment | **Explicitly not one.** The labels are file-reading results; transitive dependencies may carry other licenses. | `UPSTREAM_REFERENCES.md:30` |
| AI Scientist v2's custom license terms | **Not read** — repo not cloned. Must be read before any use beyond study. | `UPSTREAM_REFERENCES.md:44,83` |
| "External contributor can build without clones" | **Untestable** — there is nothing to build (§2.5). | — |
| The pre-fix source of `checkout_upstreams.py` | **Unrecoverable** from this repository; §3.1 reproduces the mechanism, not a recovered artifact. | — |

### 4.3 One measured number did not reproduce

`UPSTREAM_REFERENCES.md:106` records a footprint of **693 MB** (`pydantic-ai` 421 MB,
`paperspine` 94 MB, `deepagents` 88 MB, `paper-qa` 60 MB, `openhands-sdk` 32 MB).
Re-measured during this evidence round on the same machine:

```bash
cd /e/labcairn-upstreams
for r in pydantic-ai paperspine deepagents paper-qa openhands-sdk; do
  printf "%-16s %s\n" "$r" "$(du -sm $r | cut -f1)"
done
du -sm pydantic-ai paperspine deepagents paper-qa openhands-sdk | awk '{s+=$1} END{print "TOTAL:",s,"MB"}'
```

Actual output:

```
pydantic-ai      421
paperspine       94
deepagents       94
paper-qa         60
openhands-sdk    32
TOTAL: 701 MB
```

**701 MB, not 693 MB; `deepagents` 94 MB, not 88 MB.** The conclusion the number
supports — `pydantic-ai` is ~60% of the total and is the one to justify when disk is
tight — is unaffected. The discrepancy is recorded rather than corrected here because
this document does not edit other documents, and because a ~1% drift between two
measurements of the same tree is exactly the kind of thing a reviewer should see.

**Resolved before the first commit.** `UPSTREAM_REFERENCES.md:106` was subsequently
corrected by the maintainer to "approximately 700 MB (re-measure locally; block
allocation and Git packing shift this)", with `deepagents` at 94 MB and the
`pydantic-ai` share stated as 60%. The drift is therefore a measurement artefact, not a
contradiction between two surviving claims.
rather than have smoothed away. `du` output also depends on the tool, filesystem
block size and whether `.git` is included.

### 4.4 Scope not attempted

`opencode`, `gpt-researcher`, `storm` and `ai-scientist-v2` were **not cloned** and
carry no SHA. OpenCode was to be read "by targeted subsystem"
(`PHASE_1_WORKORDERS.md:31`) — that targeted read has not happened. The work order
also allows that a third-party project need not be benchmarked end-to-end
(`:34`); no upstream benchmark was run, so no claim about upstream *behaviour*
under load is made anywhere. Every mechanism comparison in the ADRs is grounded in
**read source and read tests**, never in executed behaviour — which is the weaker
form of evidence, and ADR-0002 states its own test plan
(`ADR-0002:391` "Contracts and acceptance tests") as the work that would close it.

---

## 5. Reproduction guide for an external reviewer

Shortest path, assuming only a clone of the LabCairn repository and **no**
`E:/labcairn-upstreams`.

### 5.1 What you can verify with the repository alone

No network, no upstream clones, no dependencies:

```bash
git clone <labcairn-url> && cd labcairn
find . -type f -not -path "./.git/*" -not -path "*/__pycache__/*" | sort   # 12 files, no vendored source
grep -nE "^(import|from) " scripts/checkout_upstreams.py                   # stdlib only
git check-ignore -v _references/x .upstreams/x labcairn-upstreams/x         # §2.1
git ls-files | grep -iE "reference|upstream"                               # §2.1 (empty after commit)
ls tests/test_no_reference_leakage.py pyproject.toml .github/workflows      # §3.5 — all absent
grep -n "^#\{1,2\} " docs/adr/ADR-000{2,3,4}-*.md                          # §2.3
grep -ohE "\b[0-9a-f]{40}\b" docs/adr/*.md | sort -u                       # §2.2 — five SHAs
sed -n '170,179p' docs/UPSTREAM_REFERENCES.md                              # §2 checklist, incl. the unchecked item
```

This confirms: **deliverable inventory, separation of tracked source, absence of
runtime/CI dependency, ADR count and structure, and the fact that isolation is not
yet executable.** It is most of §1, §2.1, §2.2, §2.3, §2.5, §2.6 and §3.5.

The §3.1 fix can also be reproduced without any upstream clone, using the stand-in
repository trick in §3.1 — that is deliberately the one experiment that works
offline.

### 5.2 What you cannot verify without cloning upstream yourself

Everything in §2.4 and §3.2–§3.4 depends on the study clones. Cloning them is your
own decision: it costs ~700 MB, and — read this before you do — **cloning is safe,
executing is not.** Per `UPSTREAM_REFERENCES.md:140`, do not `pip install`, do not
run install/build/test scripts, do not run Docker Compose, and do not load bundled
skills. Everything in §3.2–§3.4 is pure read-only inspection: `find`, `grep`,
`sed`, `git rev-parse`, `ls`.

If you clone, expect **different SHAs**. Then:

- §3.2 (`paper-qa` AGPL) reproduces **regardless of SHA** — the licence boundary is
  structural and stable.
- §3.4 (the 139-file count) will drift as upstream adds or removes skill files. The
  *shape* of the finding (hundreds of files whose purpose is to instruct an agent)
  reproduces; the exact number will not.
- §3.3 (`deepagents`) and every line-number citation in the ADRs reproduce **only**
  if you land on `825acb3c…`. You probably will not; treat a mismatch as expected
  rather than as a falsification, and check whether the docstring has since been
  fixed — that would be a meaningful update to `UPSTREAM_REFERENCES.md:48`.

### 5.3 One command worth running first

```bash
cd <your-clone> && sed -n '146,161p' docs/UPSTREAM_REFERENCES.md
```

If you are reviewing before LC-P1-01, that section tells you exactly what the next
work order owes you, and whether it owes you anything you cannot yet check.

---

*Evidence document for LC-P1-00. Every command in it was executed on the development
machine on 2026-10-15 and its output is reproduced verbatim. Commands tagged
`[upstream]` were run against `E:/labcairn-upstreams`, which is untrusted third-party
reference data, read-only inspected — never executed, never vendored, never
committed. Where a claim is an assumption rather than a measurement, it says so.*
