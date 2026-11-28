# The encoding sweep: every text pipe says which encoding it decodes

**Date:** 2026-11-28
· **Scope:** the whole tree — `src/`, `scripts/`, `examples/`, `tests/`,
`.github/`
· **Witness:** `tests/test_child_encodings.py`
· **The named answers:** `tests/child_encoding.py`
· **Changes no product behaviour:** true. Every edit is to a *reader* of a
child's output, or to the encoding a child is told to write in.

---

## 1. What this is

On 2026-11-28, twice in one afternoon, a whole-suite run failed for the
same reason and nothing in the tree said so. A child process was run with
`text=True` and no `encoding=`, so the parent decoded the child's UTF-8
bytes with **the host's code page** — GBK on this machine — and the decode
raised inside `subprocess`'s reader thread, where the exception is
swallowed. The capture came back as `None`, and the caller died on
`None.strip()` — a message that names neither the cause nor the fix. Each
of the two failures cost a run of the whole suite.

**One instance of a class is not the class.** This document is the sweep
that reads the tree rather than extrapolating from the two instances, and
it found **30 text pipes** that decoded with whatever the host said.

## 2. The property, and what it takes to hold it

> A child's bytes are decoded as the encoding they were written in.

**Both halves have to agree, and which half is wrong depends on who writes
the bytes.** Pinning only the parent's half turns the failure around
rather than fixing it: a parent told to read UTF-8 while the child still
writes the machine's code page fails exactly the same way.

The measurements below are the tree's own, taken on this machine with the
project's own CPython 3.12, and they are what the constants in
`tests/child_encoding.py` say.

| The child | What it writes | How that was measured |
|---|---|---|
| `git` | **UTF-8**, unconditionally | `git rev-parse --show-toplevel` under a directory named in Chinese returns UTF-8 bytes (`b'...\xe4\xb8\xad\xe6\x96\x87...'`) and they raise `UnicodeDecodeError` under cp936. Git converts from the wide-character filesystem itself, whatever the locale is. |
| This repository's console script | **UTF-8**, by construction | `src/labcairn/cli/__init__.py` reconfigures `sys.stdout`/`sys.stderr` to UTF-8 before it writes. |
| Any other Python program | **the machine's code page** — cp936 here — unless told otherwise | A plain child writes GBK; `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` and `-X utf8` each make it write UTF-8. |
| A native tool | **its own output code page** | 7-Zip 26.02 writes GBK: listing an archive named in Chinese gives bytes that raise `UnicodeDecodeError` under UTF-8. It has an output-charset switch (`-sccUTF-8`), so it can be *asked* to write UTF-8. |

### The `-I` case, which is the tree's own sharpest edge

**Isolated mode (`-I`) ignores `PYTHONIOENCODING` and `PYTHONUTF8`.**
Measured, with the project's own CPython 3.12:

| The child is run as | Its `sys.stdout.encoding` is |
|---|---|
| `python -c ...` | `gbk` |
| `python -c ...` with `PYTHONIOENCODING=utf-8` | `utf-8` |
| `python -c ...` with `PYTHONUTF8=1` | `utf-8` |
| `python -X utf8 -c ...` | `utf-8` |
| `python -I -c ...` | `gbk` |
| `python -I -c ...` with `PYTHONIOENCODING=utf-8` | **`gbk`** |
| `python -I -c ...` with `PYTHONUTF8=1` | **`gbk`** |
| `python -I -X utf8 -c ...` | `utf-8` |

So a child run with `-I` has to be told on the command line. Four sites in
the tree were pinned the wrong way round — they set `PYTHONIOENCODING` in
the environment *and* passed `-I`, so the setting did nothing at all.

## 3. What was found, and what each call now says

**30 text pipes decoded with the host's code page. Every one of them now
states its encoding.** The sweep was AST-based (`ast.parse` over every
Python file in the tree, finding `subprocess.run` / `call` /
`check_output` / `check_call` / `Popen` calls with a `text=` or
`universal_newlines=` keyword), so it read the tree rather than
extrapolating.

### 3.1 The 30 that stated nothing

| # | Site | The child | Now says | Why that encoding |
|---|---|---|---|---|
| 1 | `tests/test_ci_shard_coverage.py` ×13 | `git` | `encoding=GIT_OUTPUT_ENCODING`, `errors=CHILD_OUTPUT_ERRORS` | Git writes UTF-8 unconditionally. |
| 2 | `tests/evaluation/cli.py` | `git` | as above | as above |
| 3 | `tests/evaluation/competitor_package.py` | `git` | as above | as above |
| 4 | `tests/test_evaluation_harness.py` | `git` | as above | as above |
| 5 | `tests/test_intake_guards.py` | `git` | as above | as above |
| 6 | `tests/test_outsider_path.py` | `git` | as above | as above |
| 7 | `tests/test_application_layer.py` ×2 | a Python child printing module paths | `encoding=PYTHON_OUTPUT_ENCODING` **+ the child's write side pinned** | The child prints the module's own path, which on a checkout under a path with Chinese characters holds characters the machine's code page cannot spell. |
| 8 | `tests/test_competitor_comparison.py` ×2 | a Python child | as above | The child's environment is pinned where it is built, so the `PYTHONPATH` it needs is not lost. |
| 9 | `tests/test_consent_demo.py` | a Python child | as above | |
| 10 | `tests/test_paper_version_demo.py` | a Python child | as above | |
| 11 | `tests/test_pilot_runbook.py` | a Python child | as above | **The site the brief named.** |
| 12 | `tests/test_parallel_temp_isolation.py` | a Python child | as above | The environment the probe is given carries the `TMPDIR` and the worker name this test is about, so the encoding variables are *added* to it rather than replacing it. |
| 13 | `tests/evaluation/runner.py` | a `pytest` subprocess | as above | The inner run writes its failure output in the machine's code page unless it is told otherwise. |
| 14 | `tests/test_ci_shard_coverage.py` (`_run_remeasure`) | a Python child | as above | |
| 15 | `examples/g2_exit_demo.py` | a Python child | `encoding="utf-8"`, `errors="replace"` + `PYTHONIOENCODING` in the child's environment | A local constant, because `examples/` has no `tests/` on its path. |
| 16 | `scripts/outsider_path.py` | the console script | `encoding="utf-8"`, `errors="replace"` | The child's output goes into a log file opened as UTF-8. See §5 for why the `text=True` here is inert. |
| 17 | `scripts/lgpl_upstream_archives.py` | **7-Zip**, a native tool | `encoding=SEVEN_ZIP_OUTPUT_ENCODING` (`"utf-8"`) **+ `-sccUTF-8`** on the command line | **The case the brief names**: a child that writes something else. 7-Zip writes GBK by default; it is asked to write UTF-8, and the parent decodes UTF-8. |

### 3.2 The 13 that stated an encoding but no `errors=`

A decode that raises inside the reader thread is swallowed, and the capture
comes back as `None`. So an undecodable byte must cost the reader a wrong
character and never a dead stream. These sites now say
`errors=CHILD_OUTPUT_ERRORS` (`"replace"`):

`tests/test_chinese_run_classes.py` (1), `tests/test_chinese_totals_pin.py`
(3), `tests/test_fake_provider_determinism.py` (1),
`tests/test_fake_provider_isolation.py` (1),
`tests/test_pilot_feedback_ingest.py` (1),
`tests/test_provider_credentials.py` (1), `tests/test_release_workflow.py`
(4), `scripts/notice_licence_watch.py` (1).

### 3.3 The arrow turned round: 4 sites where the child wrote the code page

These already said `encoding="utf-8"` — and were **broken anyway**, because
their children wrote the machine's code page. Each now pins the child's
write side as well:

| Site | What was wrong | What it says now |
|---|---|---|
| `tests/test_chinese_run_classes.py` | `-I` + no write-side pin | `-I -X utf8` + `PYTHON_OUTPUT_ENCODING` |
| `tests/test_chinese_totals_pin.py` (×2) | `-I` + no write-side pin | `-I -X utf8` + `PYTHON_OUTPUT_ENCODING` |
| `tests/test_fake_provider_isolation.py` | `-I` + `PYTHONIOENCODING` in the env, which `-I` ignores | `-I -X utf8` |
| `tests/test_pilot_feedback_ingest.py` | no write-side pin | the child's environment is built through `python_child_environment()` |

`tests/test_approval_crash_matrix.py` and
`tests/test_release_workflow.py` also had a Python child whose write side
was not pinned; they now pin it too.

### 3.4 Left alone, with the reason

| Site | Why it was left |
|---|---|
| `src/labcairn/**` | **The product does not decode a child.** There is no `subprocess` call in `src/` at all — only the word "subprocess" in a comment and in the capability list. Nothing to change. |
| `web/src/**/*.ts` | The one `execFileSync` that reads output already says `encoding: 'utf8'` (`web/src/thirdPartyNotices.test.ts`). The other (`web/src/api/bundle.test.ts`) passes `stdio: 'ignore'`, so it reads nothing at all. |
| `shell/src/**/*.mjs` | The Electron tree spawns the service and reads its stdout as **bytes** (`Buffer.from(chunk)`), decoding a chunk at a time with `.toString('utf8')` — and the child's output is this repository's own, which is UTF-8. There is no host-code-page decode to fix. |
| `.github/remeasure_shards.py` | Already states `encoding="utf-8"` and `errors="replace"` on both its `gh` and `git` calls. |
| `scripts/check_repo_root.py`, `scripts/checkout_upstreams.py` | Already state `encoding=GIT_OUTPUT_ENCODING` and `errors="replace"`. These two are where the tree's convention was born; the sweep adopted it rather than replacing it. |
| `scripts/check_external_paths.py`, `scripts/build_external_path_ledger.py` | Their `read_text` calls go through a helper that does `path.read_bytes().decode("utf-8", errors="replace")` — the encoding is stated, one layer down. The four remaining `read_text` calls with no encoding in the tree are all calls to that helper. |
| `examples/g1_exit_demo.py` | One `read_text()` with no encoding, on a file the demo itself wrote with `encoding="utf-8"` two lines earlier. It was a file read, not a child's output, and it was left alone — and then **fixed anyway**, because it is the same defect class and the cost of fixing it is one keyword. It now reads with `encoding="utf-8"`. |
| `scripts/cjk_ceilings.py`, `scripts/run_ourside_competitor.py`, `scripts/run_paperqa_competitor.py`, `scripts/pilot_redaction.py` | Every `.decode()` in them names its encoding (`"utf-8"`, with `"replace"` where a byte may be lost). |
| `scripts/outsider_path.py` (`response.read().decode("utf-8")`) | The encoding is stated. |

## 4. The witness

`tests/test_child_encodings.py`, five tests.

**`test_every_text_pipe_states_the_encoding_it_decodes`** — a static gate
over every `subprocess` call in `src/`, `scripts/`, `examples/`, `tests/`
and `.github/`. It fails by naming the file, the line, and which half is
missing, so the fix is where the failure is. It requires both `encoding=`
and `errors=`.

**`test_a_text_pipe_states_an_encoding_that_is_one_of_the_known_ones`** —
a stated encoding has to be one this repository has a *name* for, because
an unnamed encoding is a fact nobody wrote down.

**The gate also watches the tree's own wrappers.** The tree has a shared
helper that runs a command with a deadline (`tests/deadline_support.py`,
added by the deadline sweep on the same day), and a text pipe routed
through it is still a text pipe: the helper forwards its keyword arguments
to `subprocess.run`, so the encoding still has to be stated at the call
site. **This was checked, not assumed** — the witness was run against the
deadline sweep's branch, where it found **38** sites without an encoding,
including the ones routed through `bounded_run` / `bounded_git`. A gate
that only recognised `subprocess.run` would have gone quiet the day the
tree grew a wrapper, and the wrapper is exactly where a reader would stop
looking. The wrapper names are listed in
:data:`~tests.test_child_encodings.CHILD_RUNNER_NAMES` rather than matched
by a pattern, so a new wrapper is added there deliberately.

**`test_a_child_the_host_cannot_read_is_still_read`** — the behavioural
gate. The child writes a byte sequence that is invalid in UTF-8 *and* in
every single-byte code page (a UTF-8-encoded surrogate, `\xed\xa0\x80`),
and the reader has to hold them.

**`test_the_same_child_read_with_the_hosts_encoding_is_not_held`** — the
control, and the reason the behavioural gate has teeth: the same bytes,
decoded with the host's code page, raise.

**`test_a_python_child_writes_what_the_tree_says_it_writes`** — measures
that the child's *write* side pinning works, rather than taking it on
trust: the pinned child writes UTF-8, the ambient child writes the
machine's code page, and the two byte sequences differ.

### 4.1 The measurement that the witness fails without the fix

The mutation removes the `encoding=` and the `errors=` from one text pipe,
and the witness is expected to go red and to name that file and line.

```
$ python measure_mutation.py <worktree> <file>
=== 1. The module path the tests load ===
E:\LabCairn\.claude\worktrees\lucid-neumann-7fcfbc\src\labcairn\__init__.py
=== 2. Mutating tests\test_ci_shard_coverage.py ===
  removing the encoding= on line 389
  removing the errors= on line 390
  mutation applied
=== 3. Running the witness against the mutated tree ===
E       AssertionError: every text pipe has to say which encoding it decodes:
E         tests/test_ci_shard_coverage.py:388: reads text but states no `encoding=`; it decodes with the host's code page
E         tests/test_ci_shard_coverage.py:388: states no `errors=`; an undecodable byte must cost the reader a wrong character, never a dead stream
FAILED tests/test_child_encodings.py::test_every_text_pipe_states_the_encoding_it_decodes
1 failed, 4 passed in 5.51s
=== 4. The witness's exit status: 1 ===
THE WITNESS FAILED, as it must.
=== 5. Restored test_ci_shard_coverage.py ===
```

The same mutation on `scripts/lgpl_upstream_archives.py` — a file in a
different root, and a native-tool child rather than a git one — was
detected the same way:

```
E         scripts/lgpl_upstream_archives.py:186: reads text but states no `encoding=`; it decodes with the host's code page
1 failed, 4 passed in 5.54s
```

**The trap this measurement had to avoid.** The `.venv`'s editable install
names the **main checkout**, not the worktree, so a bare `pytest` run
imports the main checkout's tree — and the mutation then comes back
**green**, because the tests never loaded the files that were changed. The
mutation script therefore prints the module path the tests load and
**refuses to mutate anything outside the worktree**. The path printed above
is the worktree's own.

## 5. Two things the measurements corrected in the brief

**The brief said the tree's children write UTF-8. They do not — not by
default.** A plain Python child writes the *machine's* code page, which is
cp936 here. The tree's own scripts and demonstrations are UTF-8 by
convention and by the console script's reconfiguration, but a *child
process* that is not this repository's console script writes GBK unless it
is told otherwise. So the fix for a Python child is **both halves**: the
parent's `encoding=` *and* the child's write side
(`PYTHONIOENCODING`/`PYTHONUTF8`, or `-X utf8` when the child runs with
`-I`). The brief's framing — "the tree's own output is UTF-8, so a child's
output that the tree produced is UTF-8" — is true for the tree's own
programs, and it is the reason the tree's *scripts* read their own
children as UTF-8; it is not true for an arbitrary child, and the four
sites in §3.3 were broken because it was taken as true for those too.

**`text=True` on a `Popen` whose `stdout` is a file object is inert.**
Measured: `Popen.stdout` is `None` for a file object and a
`TextIOWrapper` for `subprocess.PIPE`, because a file object is passed
straight to the child and no pipe is created. `scripts/outsider_path.py`'s
service pipe is such a case — the `text=True` there decodes nothing. It
is stated anyway, because a reader who sees `text=True` and no encoding
has to assume the machine's code page, and the day someone changes
`stdout=log` to `stdout=subprocess.PIPE`, that assumption becomes the bug.

## 6. What a future change has to do

* **A new text pipe** has to state `encoding=` and `errors=`. The gate
  fails without them, naming the file and the line.
* **A new child kind** needs a named answer in `tests/child_encoding.py`,
  and a measurement of what it writes. `NATIVE_OUTPUT_ENCODING` is the
  native-tool answer, and it is UTF-8 *because the tool is asked to* — a
  tool with no charset switch would need its host's code page named
  instead, and that would be a different answer, which is the point of
  having the name.
* **A child run with `-I`** has to be told with `-X utf8`, not with the
  environment.
* **Both halves.** A parent's `encoding=` alone turns the failure around.

## 7. The other window in this batch, and what the integrating session has to do

The deadline sweep (`claude/distracted-feynman-6fc75a`, *"Give every wait in
the tree a deadline, and a witness that fails without it"*) touches **13 of
the 26 files this sweep changed**:

`examples/g1_exit_demo.py` · `examples/g2_exit_demo.py` ·
`scripts/lgpl_upstream_archives.py` ·
`tests/evaluation/competitor_package.py` ·
`tests/test_application_layer.py` · `tests/test_chinese_run_classes.py` ·
`tests/test_chinese_totals_pin.py` · `tests/test_ci_shard_coverage.py` ·
`tests/test_evaluation_harness.py` · `tests/test_outsider_path.py` ·
`tests/test_parallel_temp_isolation.py` · `tests/test_pilot_runbook.py` ·
`tests/test_release_workflow.py`

**What the two sweeps do to the same lines.** The deadline sweep replaces
`subprocess.run` with `bounded_run` / `bounded_git`; this sweep adds
`encoding=` and `errors=` to those same calls. The two edits are to
different keywords of the same call, so **Git merges them automatically** —
measured: `git merge --no-commit claude/distracted-feynman-6fc75a` from this
branch reports *"Automatic merge went well"*, with no conflict.

**But a merge is not the end of it, and this is the part that matters.**
On the merged tree, the deadline sweep's call sites are `bounded_run(...)`
and `bounded_git(...)` rather than `subprocess.run(...)`, and **they still
have no encoding** — the deadline sweep had no reason to add one. This
sweep's edits are in the same call, so they come across; but the sites the
deadline sweep *added* (where it introduced a wrapper call that was not
there before) and the sites this sweep did not reach would be caught by the
witness on the merged tree.

**Measured: the witness was run against the deadline sweep's branch and
found 38 sites without an encoding there**, including every wrapper site.
So the merged tree will not be green until the wrapper sites carry an
encoding as well — and the witness names each one.

**What the integrating session has to do**, beyond the usual merge:

1. Register `tests/test_child_encodings.py` in `tests/evaluation/manifest.py`
   and in `.github/ci-shards.json`, and measure its cost on a runner.
2. Add `encoding=`/`errors=` to the wrapper call sites the deadline sweep
   introduced, where this sweep did not reach them. The witness names
   them.
3. Re-measure the shard costs, because this sweep adds two test files and
   changes a dozen.

## 8. What was measured, and what was run

| Command | Result |
|---|---|
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `593 files already formatted` |
| `mypy --strict` | `Success: no issues found in 518 source files` |
| `pytest tests/test_child_encodings.py` | `5 passed` |
| `pytest tests/test_child_encodings.py tests/test_chinese_totals_pin.py tests/test_chinese_run_classes.py tests/test_parallel_temp_isolation.py` | `26 passed` |
| `pytest tests/test_application_layer.py tests/test_consent_demo.py tests/test_paper_version_demo.py tests/test_competitor_comparison.py tests/test_fake_provider_determinism.py tests/test_fake_provider_isolation.py` | `152 passed` |
| `pytest tests/test_ci_shard_coverage.py tests/test_intake_guards.py tests/test_provider_credentials.py tests/test_pilot_feedback_ingest.py` | `103 passed, 3 failed` — see below |
| `pytest tests/test_pilot_runbook.py tests/test_outsider_path.py tests/test_release_workflow.py tests/test_evaluation_harness.py` | `174 passed, 5 failed` — see below |

**The failures, and what each one is.**

Three of the five in the last row are this sweep's own consequence, and
they are the integrating session's to settle: `tests/test_child_encodings.py`
is in no gate class and in no shard, so `tests/test_evaluation_harness.py`
and `tests/test_ci_shard_coverage.py` say so. The file has to be registered
in `tests/evaluation/manifest.py` and in `.github/ci-shards.json`, and its
cost has to be measured on a runner.

The other two are **not** this sweep's:

* `tests/test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on`
  fails because `tests/test_drill_rewrite_interrupted.py` changed since the
  shard costs were measured, and that change came from `5d54391c` — *"Give
  the drill tests' wait a deadline, and make the injector fire on the write
  it names"* — which is on `main` and is not this sweep's work.
  **Verified by running that one test on the pristine tree** (this sweep's
  changes stashed aside): it fails there too, with the same assertion.
* The four `tests/test_outsider_path.py` failures were an artefact of the
  way the run was invoked, and they are worth recording because they are
  the same trap as the editable install. The run set
  `PYTHONPATH=$PWD/src`, and `scripts/outsider_path.py` does **not** clear
  `PYTHONPATH` for the clone it makes — so the clone imported this
  worktree's `labcairn` rather than its own, and the witness
  *"the walk runs the clone's own code, not the developer's"* correctly
  failed. Re-run with `PYTHONPATH=` (unset): the whole file **passes** —
  `17 passed in 142.31s`. The tree's own rule — set `PYTHONPATH` to the
  worktree's `src` so the tests load the worktree — collides with a test
  that measures whether a *clone* is isolated from the developer, and the
  two cannot both be satisfied in one environment. **A test that measures
  clone isolation has to be run without `PYTHONPATH` set**, and that is
  worth knowing before the next run.

**The `mypy --strict` scope.** It is run with the configured scope
(`files = ["src", "conftest.py", "tests"]`). Run over `scripts/` and
`examples/` as well it reports 99 errors — **all pre-existing**, and
outside the scope CI checks. `scripts/` and `examples/` are not
type-checked by the `lint` job.

## 9. The files this changed

`examples/g1_exit_demo.py` · `examples/g2_exit_demo.py` ·
`scripts/lgpl_upstream_archives.py` ·
`scripts/notice_licence_watch.py` · `scripts/outsider_path.py` ·
`tests/evaluation/cli.py` · `tests/evaluation/competitor_package.py` ·
`tests/evaluation/runner.py` · `tests/test_application_layer.py` ·
`tests/test_approval_crash_matrix.py` · `tests/test_chinese_run_classes.py` ·
`tests/test_chinese_totals_pin.py` · `tests/test_ci_shard_coverage.py` ·
`tests/test_competitor_comparison.py` · `tests/test_consent_demo.py` ·
`tests/test_evaluation_harness.py` · `tests/test_fake_provider_determinism.py` ·
`tests/test_fake_provider_isolation.py` · `tests/test_intake_guards.py` ·
`tests/test_outsider_path.py` · `tests/test_paper_version_demo.py` ·
`tests/test_parallel_temp_isolation.py` · `tests/test_pilot_feedback_ingest.py` ·
`tests/test_pilot_runbook.py` · `tests/test_provider_credentials.py` ·
`tests/test_release_workflow.py` · `tests/child_encoding.py` (new) ·
`tests/test_child_encodings.py` (new) ·
`docs/acceptance/child-encoding-sweep-2026-11-28.md` (this document)

**No file under `src/` changed.** The product does not decode a child.
