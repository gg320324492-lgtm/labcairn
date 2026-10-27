# G5 — Independent review of the documents, the claims and the release contents

**Gate:** G5 — the public alpha · **Work orders:** LC-P1-13 (evaluation, fault
injection and competitor baseline) and LC-P1-14 (public alpha handoff and
review dossier).
**Scope:** the records and the package — §4.1 and §4.2 of
[`docs/plans/LC-P1-13-14-task-breakdown.md`](../plans/LC-P1-13-14-task-breakdown.md),
and the seven clauses this review was given.
**Reviewer:** an independent reviewer dispatched for G5. **I wrote no fix into
this repository.** Every change I made was made to break something, and every
one was reverted.
**Measured commit:** `72154cd27fc99005ab1ee22c6d5e58608e6b5b2f`. `git rev-parse
HEAD` in my worktree returned exactly this, so I measured the gate commit and
checked nothing else out.
**Re-verified against:** `8c0eb403c70c161b41a2f8e1407613307a7e6cf9` — **§16**,
which re-runs every one of the fourteen findings' own mutations against the
fixed tree and adds what the re-verification found. **§§1–15 describe the
gate commit; §16 describes the re-verification, and where the two disagree,
§16 is the later reading and the measurement is in §16.3.**
**Worktree:** `E:\LabCairn\.claude\worktrees\agent-a931269a76040f128` — an
isolated copy of the repository. **The main checkout was not measured.**
**Date:** 2026-10-25.
**Environment:** Windows 11 Pro 10.0.26200 (x86_64), Python 3.12.13 (the
interpreter `.python-version` pins), uv 0.11.21. `--basetemp` was
`E:\labcairn-local\bt-g5-records`, outside the repository; every process had
its own `TEMP`/`TMP`/`MPLCONFIGDIR` under
`E:\labcairn-local\tmp-g5-records`. Two runs never shared a base temp
directory.

---

## 1. The verdict

**PASS WITH NOTES** for the scope I reviewed — with **two notes that are
material to the owner's open §1.4.1b decision, and that must be read before
that decision is taken.**

**In one sentence:** every shipped document I could measure is true of this
tree, the release contents are correct when built and checked, and the
dossier's independence claims are earned — but several of the gate's own
records have aged (the blocker table, the release notes' limitation list, the
member counts, the suite size, the harness's own `NOT_MEASURED` reasons),
several watch-gaps in the gate's own machinery are recorded nowhere, and the
record the owner is being asked to decide from (§1.4.1b) rests on a
misattribution that changes the shape of the decision.

**This verdict closes nothing.** G5's exit test — *"outsider fresh install, 3
fixtures, fault injection, docs and real-provider smoke"* — names a
real-provider smoke that has not run, and the gate's own
[release notes](../RELEASE-NOTES.md) say so. My §7 gives the owner the
material to take that decision; it does not take it.

---

## 2. The method

A claim that is stated and not watched is not held. So for every claim I
found a change that would make it red, applied it, and looked at **which**
test went red.

Three rules, held to:

- **A change that changes nothing is not a mutation.** It is a finding about
  the test.
- **A change whose anchor did not match is not a survivor.** It means nothing
  was tested.
- **The test that went red is named**, not "the suite went red".

Every surviving mutation was **read by hand** before it was called a finding.

**Where the mutations ran.** Mutations to the repository's own files were made
in my worktree and reverted (`git checkout --`); each was confirmed reverted
with `git status --short` before the next. Mutations that needed a *built
artefact* or a *fresh commit* (the release gate's member lists, the dossier's
anchor counting) ran in a **throwaway copy of the tree outside the
repository**, made with `git archive HEAD | tar -x`, so the review's own
worktree was never dirty and no commit was ever made here. The one mutation
of a *test file* (removing a stale skip) was made in my worktree and
reverted.

**One environment note, because it cost me five failures and it is worth
recording.** On Windows, `tempfile.gettempdir()` consults **`TMPDIR` first**,
before `TEMP` and `TMP`. The repository's root `conftest.py` sets `TEMP` and
`TMP` for a parallel worker but **not** `TMPDIR`, so an ambient `TMPDIR`
silently defeats the isolation — see **F4**. My first whole-suite run set
`TMPDIR` as well as `TEMP`/`TMP`, and two tests went red for that reason and
for no other. The re-run without `TMPDIR` passed.

---

## 3. The baseline, measured

| Run | Command | Outcome |
|---|---|---|
| The whole suite | `pytest tests/` on the gate commit, one process | **3467 passed, 7 skipped, 5 failed** in 1816.72 s |
| Two of the five failures, re-run | `pytest tests/test_parallel_temp_isolation.py` **without** `TMPDIR` | **3 passed** — the two failures were my `TMPDIR` (**F4**) |
| The three failures, re-run | `pytest tests/test_outsider_path.py` alone, **without** `TMPDIR` and without the concurrent `uv build` / `uv pip install` I had running | **16 passed in 193.41 s** — the walk's own SQLite database reported a `disk I/O error` in the failing run; it does not reproduce in isolation (**F13**) |
| The scoped witnesses | `tests/test_threat_model.py`, `tests/test_review_dossier.py`, `tests/test_public_fixtures.py` | **87 passed** |
| `tests/test_release_workflow.py` | | **8 passed** |
| `tests/test_readme_accuracy.py` | | **18 passed** in 106.36 s |
| **The evaluation harness on this tree** | `python -m tests.evaluation --out E:\labcairn-local\tmp-g5-records\evaluation` | **exit 2** — *"a selected class could not be run"* — after 1793.1 s. Unit 1510/1511, Integration 1131/1134, Negative 361/364, E2E 102/102, Repository gates 369/369, **Real-model smoke NOT RUN**; **two of the six blockers FAILED**; no comparison made and no ranking printed |

**The seven skips**, and what each one is:

| The skip | What it is |
|---|---|
| `tests/test_api.py:520` | a declared POSIX conditional |
| `tests/test_security_paths.py:156` | a declared POSIX conditional |
| `tests/test_security_paths.py:453`, `:486` | 8.3 short names are disabled on **this** volume (`E:`), so the two short-name witnesses cannot run here |
| `tests/test_provider_credentials.py:285` | `requires_provider` — the real-provider smoke |
| `tests/test_earlier_exit_demos.py:218`, `:266` | `g1_exit_demo` skipped "until the product's 8.3 short-name comparison is fixed" — **the defect was fixed before this commit; see F1** |

**A second, independent witness that the tree is green.** The evaluation
harness runs the whole suite as its own subprocess, and **its** run of the
same tree reports **zero failed and zero errored cases in every class** —
Unit 1510/1511, Integration 1131/1134, Negative 361/364, E2E 102/102,
Repository gates 369/369, with the seven skips and the real-model smoke
NOT RUN. Two whole-suite runs on the same commit therefore agree: the five
failures in my run were environmental, and **the tree at `72154cd` is green
on this machine.**

---

## 4. Clause 1 — every command in the README is extracted and run, and the two language versions agree

**What the claim is.** `docs/plans/LC-P1-13-14-task-breakdown.md` §4.2
clause 4: *"every command in the README is extracted and run — a command that
is in the README and is not in the extraction is a failure"*, carried by
`tests/test_readme_accuracy.py`.

**Baseline.** `tests/test_readme_accuracy.py` — **18 passed**.

**M1a — the narrow attack. RED, and the named test is the right one.**
`uv run pytest --lf` inserted into README.md's English shell block.

> `tests/test_readme_accuracy.py::test_readme_documents_only_verified_commands` —
> **RED**: *"README documents command(s) with no verified row …: ['uv run
> pytest --lf']"*

The fail-closed direction holds for README.md. `test_verified_commands_are_all_documented`
stayed green, which is correct — it watches the other direction.

**Measured, not assumed.** The three command surfaces in the repository carry
**the same eleven commands** today — README.md's English block, README.md's
Chinese block, and README.zh-CN.md — read out of the fenced blocks with the
extractor the test itself uses.

**M1b — the same command in the Chinese README. GREEN, and nothing watches
that file at all.** `uv run pytest --lf` inserted into `README.zh-CN.md`.

> `pytest tests/test_readme_accuracy.py tests/test_status_consistency.py` —
> **148 passed, 0 failed.**

A grep of the whole `tests/` tree for `zh-CN`, `README.zh` finds **zero**
hits: **no test in this repository reads `README.zh-CN.md`**. The two READMEs
each state that they agree — README.md line 168 (*"两处内容一致"*) and
README.zh-CN.md line 5 (*"两者内容一致"*) — and nothing watches it.

**This gap is recorded.** `CONTRIBUTING.md` §12 says so in as many words:
*"The README's Chinese section and `README.zh-CN.md` must say the same thing.
Nothing watches that, because the documents were written under a file-ownership
contract that did not include `tests/`."* A gap the repository names is a note;
a gap it does not name is a finding.

**M1c — the same command in a non-shell fence. GREEN.** A ```console block
carrying `uv run pytest --last-failed` appended to README.md: the README gate
is **green** (15 passed). I then ran **both** extractors in the gate over the
mutated README — `tests/test_readme_accuracy.py::documented_commands` and
`scripts/outsider_path.py::readme_commands` — and **neither** sees the
command (22 commands each, neither containing `--last-failed`).

**M1d — the same command in an inline code span. GREEN.** An inline
`` `uv run pytest --last-failed` `` in README prose is invisible to the
extractor, which reads fenced blocks only.

**M1e — a non-shell fence *between* two shell fences. RED for the wrong
reason, and it is worth reading.** The same ```console block inserted *before*
the first shell block turned the gate red with:

> *"README documents command(s) with no verified row …: ['Requires
> [uv](https://docs.astral.sh/uv/) (Python 3.12 is provisioned by it) …',
> 'Python side, from the repository root:', '```bash']"*

The extractor mis-paired the fences and read **prose** as commands, and the
command it should have caught was **dropped**. This is the bug the gate's own
walk script was written to avoid — `scripts/outsider_path.py::fenced_blocks`
pairs fences fence by fence and filters on language, and its own docstring
says: *"the blocks are paired fence by fence rather than matched by a
pattern, because a pattern that looked for 'the next closing fence' would
read a ```python block as the tail of the shell block above it."* **The two
extractors in this gate disagree, and the one the README gate uses is the
pattern-based one.**

**Verdict on clause 1.** The claim **holds for README.md's shell blocks** and
is witnessed by a test with teeth. It does **not** hold for
`README.zh-CN.md`, for a command in any other fence, or for a command written
as an inline code span. The Chinese-README gap is recorded; the other two
are not — see **F6**.

---

## 5. Clause 2 — the artefact examples are real

**What the claim is.** §4.2 clause 5: *"the examples in the README and the
quickstart are the fixtures' real artefacts, produced by the code, not drawn
by hand."*

**First, a measurement that changes what the clause is about.** **There is no
artefact example in README.md, README.zh-CN.md or `docs/QUICKSTART.md`.**
Every fenced block in the two READMEs is a shell block; the quickstart has
shell blocks and one ```markdown prose block (the three lines of `notes.md`).
The documents **name** artefacts and **name** fields; they do not **show** an
artefact. The clause's subject is empty — which is not a failure, but it
means the clause can only be discharged by checking the documents' *artefact
facts*, and that is what I did.

**The artefact facts, checked against the code by running it.** A workspace
outside the repository, the quickstart's own commands:

| The document says | What the code produced |
|---|---|
| quickstart §4.2: *"The JSON names what it made — `root`, `database_path`, `migration_revision`, `source_dirs`, `created` and `policy_digest`"* | `labcairn --workspace ./workspace init --json` → exactly `{root, database_path, migration_revision, source_dirs, created, policy_digest}` — six fields, the same spelling |
| quickstart §4.4: *"The JSON's `bound_source_ids` names the three sources"* | `task create --json` → `bound_source_ids` with **three** ids |
| quickstart §4.6: *"It reports one source as the ledger holds it: `kind`, `display_name`, `relative_path`, `content_sha256`, `size_bytes` and `readability`"* | `sources inspect --json` → the `source` object carries exactly those six fields |
| quickstart §4.7: *"`report/v1/` holding `report.json`, `report-manifest.json`, `report.md`, `report.html`, `report.docx` and `report.pdf`"* | `src/labcairn/reports/revisions.py` writes exactly those six: `DOCUMENT_FILENAME = "report.json"`, `MANIFEST_FILENAME = "report-manifest.json"`, and `report.{md,html,docx,pdf}` from `_FORM_SUFFIX` |

**The byte comparison.** The quickstart tells the reader to copy two fixture
files as the research material. I copied them and hashed both sides:

| The quickstart's example | The fixture it names | SHA-256 | Byte-identical |
|---|---|---|---|
| `materials/paper.pdf` | `tests/fixtures/papers/arx-2610.10596.pdf` | `6da9f8057e8cc7bafcf76316d660276f40c2e4a87230fa418e28cde51143d700` | **yes** |
| `materials/measurements.csv` | `tests/fixtures/analysis/groups.csv` | `1c74e71d72ce676838e78fc4aeb7cd7303e210268430b5fe143e83173226373f` | **yes** |

The PDF's hash **appears in `tests/fixtures/papers/MANIFEST.md`**, and
through the product's own machinery the PDF's `readability` is `readable` —
which the quickstart makes a condition of the path ("A PDF whose text layer
cannot be read is **not** a substitute").

**Nothing watches this.** No test reads `docs/QUICKSTART.md` except the
relative-link resolution in `tests/test_status_consistency.py`. The
quickstart's own §8 admits the gap for the *command list*; the *field names*
and the *artefact file list* are not named as unwatched.

**Verdict on clause 2.** The artefact facts the documents state are **true of
this tree**, measured by running the code and by hashing bytes. The
documents contain no artefact example, so the clause is discharged in
substance and vacuous in letter. The facts are unwatched — see **F6**.

---

## 6. Clause 3 — the threat model's references resolve, and its claims are earned

**What the claim is.** §4.1 clause 6: *"the threat model names every write
and every network reach"*.

**Baseline.** `tests/test_threat_model.py` — **34 passed**.

**M3a — break a citation. RED, and the named test is the right one.**
`src/labcairn/workspace/outputs.py:150` → `:9999`.

> `tests/test_threat_model.py::test_every_citation_resolves_to_a_file_and_a_line` —
> **RED**: *"these citations in the threat model do not resolve, so they are
> not evidence: src/labcairn/workspace/outputs.py:9999 is past the end of the
> file"*

**The count the document claims.** The threat model names **136**
`path:line` citations. The watching regex matches **136** of them and
**misses one**: `pyproject.toml:316`, because the regex's extension list is
`py|ts|tsx|md|json|html`. That citation resolves today (`pyproject.toml` has
332 lines; line 316 is the `requires_network` marker definition). The
witness table's **fourteen** claim ids are contiguous from C1 and each has a
test whose name is about it — the witness says so and the witness is
watched.

**The write enumeration, measured.** §1.2 says
`src/labcairn/workspace/outputs.py` *"is the only place in LabCairn that writes
a file"* and tabulates **six** writes outside it. I enumerated every write
primitive under `src/labcairn/`: `outputs.py` (the one path), plus
`api/session.py` (the token), `api/typescript.py` (the contract),
`cli/workspace.py` (the config and the policy),
`analysis/chart/render.py` (the matplotlib config and font cache), and
`cli/commands.py` (the directories). `security/approval.py`'s `open("rb")`
and `material/pdf.py`'s `pdfplumber.open` are reads. **The enumeration is
accurate at this commit.**

**M3b — add a seventh write. GREEN — a survivor.** A new module
`src/labcairn/telemetry.py` whose `record()` calls `path.write_text(...)`:

> `pytest tests/test_threat_model.py tests/test_security_paths.py
> tests/test_workspace_boundaries.py tests/test_no_reference_leakage.py
> tests/test_ci_shard_coverage.py tests/test_application_layer.py
> tests/test_analysis_report_manifest.py tests/test_material_walk.py
> tests/test_capability_namespaces.py` — **353 passed, 3 skipped**

Nothing scans `src/` for write primitives and compares them with the
threat model's table. The C6 witness watches the *property* — a write aimed
at a source root is refused — and not the *enumeration*.

**Verdict on clause 3.** The citations resolve, the witness has teeth, the
network claim (C13) is watched by a scan of the whole source tree, and the
write enumeration is accurate. The enumeration can fall behind silently —
see **F7**.

---

## 7. Clause 4 — the dossier's references resolve, and its independence claims are earned

**Baseline.** `tests/test_review_dossier.py` — **12 passed**.

**M4a — move an upstream anchor to the neighbouring line. RED, twice.**

> `tests/test_review_dossier.py::test_every_upstream_anchor_is_a_line_that_exists`
> — **RED**: *"these upstream anchors do not point at anything: :51 is a blank
> line of docs/UPSTREAM_REFERENCES.md"*
>
> `tests/test_review_dossier.py::test_the_dossier_cites_each_load_bearing_anchor_as_often_as_it_claims`
> — **RED**: *"the dossier's upstream anchors and the catalogue have come
> apart: :50 is cited 0 time(s) and should be cited 1 time(s)"*

**M4b — corrupt one character of PaperQA2's commit SHA. RED.**

> `tests/test_review_dossier.py::test_the_dossier_names_a_sha_only_for_a_repository_that_was_cloned`
> — **RED**: *"the dossier names commit SHAs the catalogue does not record:
> 57e89f7223b0960d5ee5ea048c69e3c47e088573"*

The dossier's own §5.4 mutation table claims five corruptions were each
caught; I re-ran two of the five and both were caught by the test the table
names. All **61** of the dossier's `path:line` citations match the watching
regex; **none** is unwatched.

**The independence claims, measured against the tree rather than believed:**

| The dossier says | What I measured |
|---|---|
| §4.2 check 3: the ten upstream identifiers have **zero** hits in `src/` | **zero hits** — confirmed for `CANNOT_ANSWER_PHRASE`, `GROUP_PREFIXES`, `PRECISE_LOCATOR_RE`, `_check_fs_permission`, `should_confirm`, `ConfirmationPolicyBase`, `sanitize_messages`, `UsageLimits`, `TodoListMiddleware`, `EventLog` |
| §4.3: `pydantic-ai` *"is imported in three modules"*, at named lines | **exactly three** modules, at exactly the lines named: `pydantic_models.py:137-138` and `:149-150`, `probe.py:473-476`, `adapter.py:520-523` |
| §4.2: `FailureKind` is *"an upstream enum name, and LabCairn has one at `src/labcairn/providers/errors.py:60` — with its own twelve members"* | `src/labcairn/providers/errors.py:60` — **twelve** members, confirmed |
| §4.2: the other coincident names *"occur in `src/` only inside comments and docstrings"* | confirmed — `ModelProfile`, `accumulated_cost`, `SecurityRisk`, `ErrorClassification` all appear in docstrings only |
| §4.2 check 4: the upstream names in `pyproject.toml` are *"only inside comments that cite the paper-qa licence lesson — not as a dependency"* | confirmed — `paper-qa` appears at `pyproject.toml:34`, `:65`, `:93`, all in comments; no upstream package is in the dependency list |

**The dossier's one countable number, re-measured.** §5.3: *"**2292 `def
test_` definitions across 106 test modules**, measured on 2026-10-25 on the
tree named at the top of this document"*. Counting `def test_` occurrences
under `tests/` and the `test_*.py` modules, at `dd08573` (the tree the
dossier names): **2292 and 106 — exactly the dossier's figures**, so the
method and the number reproduce. At the gate commit the same count is
**2310 across 108**. The dossier states its anchor, so this is a value that
has moved, not a defect; it is listed under "values re-measured" below.

**Verdict on clause 4.** The dossier's references resolve, its independence
claims are **earned** and re-derivable from the tree, and its own witness is
credible. It passes.

---

## 8. Clause 5 — the competitor baseline invents no superiority

**What the claim is.** §4.1 clause 3: *"the comparison is either like-for-like
on matched tasks, or not made; the dossier says which, and no ranking is
printed without the comparison."*

**Measured.** I grepped every shipped document — both READMEs, the quickstart,
the release notes, the dossier, the threat model, the three acceptance
records and the changelog — for the harness's own ranking words (`better`,
`worse`, `best`, `worst`, `superior`, `outperform`, `beats`, `winner`,
`loses`, `ahead`). Four hits, none of them a ranking:

- README.md:117 — *"the work that fills them in is still ahead"* (about
  unfinished work, not a comparison);
- `docs/REVIEW-DOSSIER.md:17` — *"it contains no claim that LabCairn is
  better than any upstream project"* (a negation);
- `docs/REVIEW-DOSSIER.md:101` — *"an invented or guessed SHA is worse than a
  blank"* (about SHAs);
- the two acceptance records quoting the watch list itself.

**No ranking is printed anywhere.** The mechanism is structural, not a
promise: the comparison renders **pairs** with no aggregate, and
`tests/test_evaluation_harness.py::test_the_rendered_comparison_carries_no_winners_language`
greps the **rendered** section for those words.

**The baseline record is honest about what was not done.** It takes
**Option C** (no comparison), gives five reasons each with a file, a line and
a check, and says plainly in §6: *"the work order's baseline clause is, as of
this document: half deferred (by the clause's own permission) and half
outstanding."* It also reports the harness's own two hard-coded
`NOT_MEASURED` reasons as **false of this tree** — the record correcting the
record, in the direction the project's own rule demands.

**M5 — a superiority claim in a shipped document. GREEN — a survivor.** I
added to `docs/acceptance/LC-P1-13-baseline.md`:

> *### 3.9 The comparison, and the ranking it supports*
> *On the three answerable fixtures, LabCairn outperforms PaperQA2 on citation
> support and on numeric extraction. The ranking is printed here because the
> comparison is like-for-like.*

> `pytest tests/test_evaluation_harness.py tests/test_readme_accuracy.py` —
> **green**. The rendered-report witness cannot see prose in a document.

**The control.** The same two files on the **unmutated** copy fail on one
test (`test_a_real_pytest_run_is_read_as_outcomes`, which needs a git
repository the throwaway copy does not have) — **the same single failure**,
so the mutation changed nothing and the survivor is real.

**Verdict on clause 5.** The clause is **satisfied** — no superiority is
claimed anywhere. It is **not watched**, and the watch that exists covers the
harness's output rather than the documents a reader reads — see **F3**.

---

## 9. Clause 6 — the release contents

**What the claim is.** §4.2 clause 6 and the release record: the NOTICE
travels with the artefacts, the member lists are the ones the tree implies,
every dependency's licence is read out of the distribution itself, and no
third-party font file reaches any artefact.

**Built, not assumed.** `uv build` into a directory outside the repository.
The sdist and the wheel were then read with the same two programs the
release workflow runs, **extracted from the parsed YAML** and executed
verbatim, exactly as the record's §6.4 describes.

| | Measured |
|---|---|
| the source distribution | **452 members** — the committed tree plus `PKG-INFO`, *"neither missing nor extra"*, **exit 0** |
| the wheel | **153 members** — 147 package, 6 metadata, and the six metadata members are **exactly** the declared ones |
| the NOTICE | in the sdist, and `labcairn-0.1.0.dist-info/licenses/NOTICE` in the wheel |
| fonts | **no** member of either artefact has a font suffix |
| the wheel's binaries | **none** — every package member is `.py` or `.typed` |
| third-party material | the three fixture papers and their manifest, and nothing else |

**The dependency licences, read out of the distributions.** `uv export
--frozen --no-dev` resolves **171 requirement lines** (the record's figure,
reproduced). A clean virtualenv was built from that export and the workflow's
own licence-audit program was run against it:

> `platform: win32` — sixteen distinct licences — **"every one of the 168
> installed distributions carries a licence the release records"** — **exit 0**

**The NOTICE's font census, reproduced from the installed distributions.**
matplotlib's `mpl-data/fonts/` holds **40** TrueType files (42 files, two of
which are `LICENSE_DEJAVU` and `LICENSE_STIX`), **14** `pdfcorefonts/` AFM
files (15 files, one of which is `readme.txt`) and **47** `afm/` AFM files —
**101 font files**, as the NOTICE says. reportlab's `fonts/` holds **18**
`.pfb`, **2** `.afm` and **5** `.ttf` — **25 font files**, as the NOTICE says —
plus `DarkGarden.sfd` and six `.txt` notices. `DarkGarden-copying.txt` is
**1,318 bytes** and names the GNU General Public License and the font's own
exception; `DarkGarden-copying-gpl.txt` is **17,976 bytes and 344 lines**.

**M6a — a real GPL v2 font reaches the artefact. RED.** A genuine
`DarkGardenMK.pfb`, taken from the installed reportlab, planted in the tree
of a throwaway copy:

> `::error::labcairn-0.1.0.tar.gz carries font files:
> ['tests/fixtures/papers/fonts/DarkGardenMK.pfb']` — **exit 1**

**M6b — the same font under an extension the check does not know. GREEN.**
The same bytes, committed as `DarkGarden.sfd` — **the font's source, which
reportlab itself ships and which the font audit counts among the seven
DarkGarden files**:

> **exit 0** — *"the release's member lists hold: neither missing nor extra"* —
> and the sdist carries `tests/fixtures/papers/fonts/DarkGarden.sfd`.

**M6c — the same bytes as a web font. GREEN.** The same file committed as
`web/src/assets/labcairn.woff2`:

> **exit 0** — and the sdist carries `web/src/assets/labcairn.woff2`.

The check is `FONT_SUFFIXES = {".ttf", ".otf", ".ttc", ".pfb", ".pfa", ".afm",
".pfm"}` — a check **by file name**. `.sfd`, `.woff`, `.woff2`, `.bdf` and
`.pcf` are font files that it does not know. The **wheel** is unaffected (it
carries no binary at all); the **source distribution** is where they land.
See **F5**.

**M6d — the NOTICE stops travelling. RED.** The NOTICE removed from the tree:

> `::error::labcairn-0.1.0.tar.gz does not carry the NOTICE`
> `::error::labcairn-0.1.0-py3-none-any.whl does not carry the NOTICE`
> `::error::… metadata members differ from the declared six` — **exit 1**

**Verdict on clause 6.** Every release claim holds when the artefacts are
built and checked, and the gate has teeth against the two obvious failures.
The font check has an extension-shaped hole — **F5**.

---

## 10. Clause 7 — the real-provider smoke, and the question §1.4.1b asks

**The question.** *Does a declared, reported skip count as a blocker that
failed?* The owner decides; I supply the material and a recommendation.

### 10.1 What the protocol actually says

I read `docs/EVALUATION.md` myself.

- Its `## Phase 1 blockers` section lists **six** bullets. **Not one of them
  requires a real provider.** They are about the clean-environment path,
  unauthorised writes, fake citations, repeated side effects, reports claiming
  verification from schema checks, and skipped required tests.
- The real-model smoke is in a **different list** — `## Mandatory automated
  gates`, item 5: *"at least one real supported provider under declared
  model/version/parameters; results and costs documented. Mock-only success is
  insufficient."*

**The two lists are not the same list, and the question is about which one a
skip falls into.**

### 10.2 What the harness's own report says, and what it does not say

The harness reports the smoke class as **NOT RUN**, gives the reason, **does
not count it as a pass**, and exits **2** — *"a selected class could not be
run"*. That is the protocol-faithful behaviour and it is the right one.

**But the record the owner is being asked to decide from misattributes the
evidence.** `docs/plans/LC-P1-13-14-task-breakdown.md` §1.4.1b says the
harness *"reported that two of the six did not hold"*, and lists them as

> * **one** because the base branch's own new witness skips G1's exit
>   demonstration until the 8.3 short-name defect of §2.6 is fixed …
> * **one** because a test declared as needing the project's own real provider
>   credentials was **skipped** — the `requires_provider` marker does exactly
>   what it says, and CI has no such credentials.*

**The second bullet is not what the harness reported.** Its own report —
`docs/acceptance/LC-P1-13-evaluation.md` §8 — attributes the second failed
blocker to a **declared POSIX platform conditional**:
`tests/test_security_paths.py::test_windows_drive_path_is_refused_on_posix`,
skipped on Windows. The baseline record says the same in §3.4: *"the
clean-environment blocker (waiting on the 8.3 defect) and the unauthorised-write
blocker (a declared POSIX-only conditional, skipped on Windows)."*

**And the provider-credential skip fails no blocker at all.** I read the
harness's own witness table, `tests/evaluation/manifest.py::BLOCKER_WITNESSES`:
the six blockers have twenty-one witness entries between them, and
`tests/test_provider_credentials.py` is **in none of them**.

**The gate's own tool says so on this tree.** I ran the harness here
(`python -m tests.evaluation --out …`, exit **2**, 1793.1 s). Its report
lists

> `tests/test_provider_credentials.py::test_real_provider_smoke_records_capabilities_and_usage`
> — **skipped** — NOT RUN. Requires the project owner's explicit authorisation
> to spend money and a credential they supplied for that purpose.

under **"### The failure cases → Unit — 1 case(s)"**, and its blocker table
gives the sixth blocker — *"Required CI tests are skipped, ignored or only
pass by mocking the actual behavior under acceptance"* — a status of
**HELD**, *"every witness was collected and passed"*, with **0** failing
cases. **The skip is a Unit-class failure case in the report, not a blocker
failure** — the gate's own measurement on the gate commit, not my reading of
a table.

**So §1.4.1b asks the owner a question using evidence that is wrong.** If the
owner reads it at its word, they will believe the provider-credential skip
failed a blocker — which is the very thing being decided.

### 10.3 The third thing: the blocker table is stale at this commit

The first failed blocker was *"g1_exit_demo is skipped on Windows until the
product's 8.3 short-name comparison is fixed"*. **That defect was fixed
before this commit** (`6220a08`, *"A new file under a short-spelled root is
under the root"*), and the skip was never removed.

**I measured it, with a control.** `C:` on this machine generates 8.3 short
names; `E:` does not. I made a directory whose short spelling is
`C:\Users\pc\AppData\Local\Temp\G5-A-V~1` and pointed the demonstration's
`TEMP`/`TMP` at it, so the defect's trigger is really present.

| | Result |
|---|---|
| the gate commit, short-spelled temp | `examples/g1_exit_demo.py` → **36 checks passed, exit 0** |
| **the control**: the same demonstration against `src/labcairn/security/paths.py` from `6220a08^` (the pre-fix path layer), short-spelled temp | **exit 1** — `WorkspaceError: WindowsPath('C:/Users/pc/AppData/Local/Temp/G5-A-V~1/tmp3ln9y_35/study/outputs/summary.md') refused: outside_every_root` — exactly the refusal §2.6 describes |

The control is what makes the first row a measurement rather than an
assertion: the same demonstration, the same machine, the same short-spelled
directory, the same failure — with one file different.

**And the witness, with the stale skip removed:**

> mutation: `KNOWN_DEFECT_ON_WINDOWS = frozenset({"g1_exit_demo"})` →
> `frozenset()`, run with the short-spelled `TEMP` —
> `pytest tests/test_earlier_exit_demos.py` — **6 passed**, no skip.

So at this commit the protocol's **first** blocker — *"A new user cannot
complete a task from a clean environment following README"* — **holds**, once
the skip that no longer describes the tree is removed. The "two of the six
blockers failed" figure in the evaluation record §8, the baseline record
§3.4 and §3.6, and the task breakdown §1.4.1b is a measurement of a tree
that is not this one.

**And the harness, run on this tree, says so — with one more thing the
records do not say.** Its blocker table, measured here at `72154cd`:

| The protocol's blocker | The harness's status here | The witness cases that did not pass |
|---|---|---|
| New user cannot complete a task from a clean environment following README. | **FAILED** | the **two stale** `g1_exit_demo` skips |
| Any unauthorized file write/escape or unconsented private-network disclosure. | **FAILED** | the POSIX-only conditional, **and the two 8.3 short-name witnesses** — *"this machine's volume has no 8.3 short names"* |
| Fake citation presented as verified or unsupported numerical fact presented as measured. | HELD | — |
| A crash silently repeats unknown file side effects. | HELD | — |
| Report claims a verified scientific result based solely on schema or rendering checks. | HELD | — |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance. | HELD | — |

**The second blocker's recorded reason is incomplete as well as
misattributed.** The baseline record §3.4 attributes it to *"a declared
POSIX-only conditional"* — one case. On this tree the harness counts
**three**: the POSIX conditional **and the two 8.3 short-name witnesses**,
which the path-layer fix of `6220a08` added to `tests/test_security_paths.py`
and which **skip on this machine's `E:` volume**. They would run on a CI
runner's `C:` volume, which generates 8.3 names — which is exactly where the
defect used to show.

**So the blocker table as it stands on this tree is: two FAILED, four
HELD — and the first of the two fails for a reason that no longer exists,
while the second fails for a reason the record does not name.**

### 10.4 The sixth blocker, read in its own words

The sixth blocker reads: *"Required CI tests are **skipped**, ignored or only
pass by mocking the actual behavior under acceptance."*

§1.4.1b paraphrases it as *"which is about a test **pretending** to pass"*.
That is **narrower than the protocol's own wording**, which lists *skipped*
as a condition in its own right, before the *pretending* half.

**And the tree today does contain a required CI test that is skipped.**
`tests/test_provider_credentials.py::test_real_provider_smoke_records_capabilities_and_usage`
carries `@pytest.mark.requires_provider` and `@pytest.mark.skip(...)`; I ran
it and it reports **SKIPPED**. `tests/test_provider_credentials.py` is in a
CI shard on **both** platforms — `ubuntu-latest` shard 3 and
`windows-latest` shard 0 of `.github/ci-shards.json`.

**The harness's report that the sixth blocker HELD is therefore not
evidence**, because none of its three witness files looks at whether any test
is skipped: `tests/test_ci_shard_coverage.py` checks shard coverage and
balance, `tests/test_fake_provider_isolation.py` checks that the
FakeProvider touches no network, and `tests/test_refusal_witnesses.py` checks
that refusal-witness phrases are read. I read all three. **Not one of them
asks whether a test was skipped.**

### 10.5 My verdict, and my recommendation

**Verdict.** *For the real-provider smoke specifically, a declared, reported
skip does **not** count as a blocker that failed* — because none of the
protocol's six blockers requires a real provider, the real-model smoke is one
of the five mandatory **gate classes** (a different list), and the harness
reports that class as NOT RUN with a reason and an exit code of 2 rather than
counting it as a pass. That is the protocol's own answer, and it is sound.

**But the reasoning in §1.4.1b is not sound**, and three things follow that the
owner must have before deciding:

1. **The premise is a misattribution** (§10.2). The provider-credential skip
   failed no blocker; the second failed blocker was a declared POSIX platform
   conditional. The decision as framed is about the wrong skip.
2. **The skip is not discharged by being declared and reported** (§10.4). Under
   the sixth blocker's plain wording, the tree contains a required CI test
   that is skipped, and **nothing in the repository would notice** — the
   harness's "HELD" for that blocker rests on witnesses that never look.
3. **The blocker table is stale** (§10.3). The first blocker holds at this
   commit once the stale skip is removed, so the "two of six" figure the
   decision rests on is not true of the tree being handed over.

**Recommendation (a recommendation, not a change).** §1.4.1b's **Option A** —
*"a declared, reported skip of the real-model smoke does not count as a
blocker that failed"* — is the right call **for the smoke**, and I recommend
the owner take it. But I recommend it **in Option C's form**, with the
protocol amended and the amendment given its own record:

- the real-model smoke is a **gate class**, not a Phase 1 blocker, and the
  gate class is **NOT RUN** — stated everywhere the gate says "ran";
- a `requires_provider` skip is **explicitly out of scope** for the sixth
  blocker, and the sixth blocker's witnesses are extended so that the
  exclusion is enforced rather than assumed.

Without the second bullet, the repository is, on the protocol's plain
wording, **in violation of its own sixth blocker today**, and no harness in
it would notice.

**And whatever is decided, the gate's exit test is not met.** The milestone
table's G5 exit test names *"real-provider smoke"*. It has not run, it
cannot run without a credential and the owner's authorisation to spend money,
and §1.4.1b's Option A's own stated cost — *"the gate's own exit test then
says the five classes ran when one of them did not"* — is the accurate
description of what would happen. **A skip does not fail a blocker; it also
does not discharge a gate class, and it does not meet an exit test.**

---

## 11. The findings, in severity order

Every finding below is reproducible from this commit.

### F1 — MATERIAL. The record the owner is deciding from misattributes which skip failed which blocker, and the blocker table it cites is stale at this commit

**Where:** `docs/plans/LC-P1-13-14-task-breakdown.md` §1.4.1b (the second
bullet), against `docs/acceptance/LC-P1-13-evaluation.md` §8 and
`docs/acceptance/LC-P1-13-baseline.md` §3.4; and
`tests/test_earlier_exit_demos.py:89` (`KNOWN_DEFECT_ON_WINDOWS`).

**What is wrong:** §1.4.1b says the provider-credential skip failed one of
the two blockers. The harness's own report — and the harness **run on this
tree** (§10.3) — says the second failed blocker was a *skip of a declared
platform conditional*, and `tests/evaluation/manifest.py::BLOCKER_WITNESSES`
shows the provider-credentials file is a witness of **no** blocker: the skip
is listed under *"The failure cases → Unit"* and the sixth blocker is
**HELD** with zero failing cases. The first failed blocker — the 8.3 one —
no longer fails: the defect was fixed by `6220a08` and the skip was not
removed. And the second blocker's recorded reason is **incomplete** as well:
on this tree the harness counts **three** failing witness cases there, not
one — the POSIX conditional **and the two 8.3 short-name witnesses**, which
skip on a volume without 8.3 names.

**How to reproduce:** run
`python -m tests.evaluation --out <outside the repository>` and read the
blocker table and the failure-cases list; then read
`tests/evaluation/manifest.py:360-394`; then run `examples/g1_exit_demo.py`
with a short-spelled `TEMP` (see §10.3 for the exact construction and the
control).

**Why it matters:** the owner is being asked to take a decision using this
evidence. Two of its three facts do not hold at the commit being handed
over, and the third is incomplete.

**Recommendation:** correct §1.4.1b's second bullet and the "two of the six"
figure before the decision is taken, and remove the stale skip — which
changes the first blocker's status from FAILED to HELD — in the same change.
Re-measure the blocker table on the tree the gate closes on.

### F2 — MATERIAL. The sixth Phase 1 blocker's "HELD" is not earned, and the tree contains a required CI test that is skipped

**Where:** `tests/evaluation/manifest.py:389-393` (the sixth blocker's three
witness files), against `docs/EVALUATION.md`'s sixth bullet.

**What is wrong:** the sixth blocker is *"Required CI tests are skipped,
ignored or only pass by mocking the actual behavior under acceptance"*, and
`tests/test_provider_credentials.py` is in a CI shard on both platforms with
a test that is skipped. None of the three witness files looks at whether any
test is skipped.

**How to reproduce:** `pytest tests/test_provider_credentials.py -rs` reports
the skip; `tests/test_ci_shard_coverage.py`, `tests/test_fake_provider_isolation.py`
and `tests/test_refusal_witnesses.py` contain no such check.

**Why it matters:** it is the difference between the harness's report being
evidence and being a tautology, and it bears directly on §10.5.

**Recommendation:** either extend the sixth blocker's witnesses to look for
skipped tests, or record the exclusion explicitly, as §10.5 recommends.

### F3 — MEDIUM. Nothing watches a shipped document for superiority language

**Where:** `tests/evaluation/report.py:50` (`RANKING_WORDS`) and
`tests/test_evaluation_harness.py::test_the_rendered_comparison_carries_no_winners_language`.

**What is wrong:** the watch greps the **rendered report's** comparison
section. The documents a reader reads are not watched. M5 (§8) put a
superiority claim into `docs/acceptance/LC-P1-13-baseline.md` and nothing
went red.

**How to reproduce:** add a sentence containing *"outperforms"* or *"better
than"* to any shipped document and run the suite.

**Recommendation:** grep the shipped records for `RANKING_WORDS` in a test of
its own, or read the word list out of the harness rather than restating it.

### F4 — MEDIUM. The parallel-run temp isolation is defeated by `TMPDIR`, and its own witness does not watch for that

*Outside the seven clauses; found while measuring them, and it changes what
the suite's greenness means.*

**Where:** `conftest.py:120-135` (`give_this_worker_its_own_temp`) and
`tests/parallel_temp_isolation.py` → `tests/test_parallel_temp_isolation.py`.

**What is wrong:** the mechanism sets `TEMP` and `TMP` for a parallel worker.
Python's `tempfile.gettempdir()` consults **`TMPDIR` first on every
platform**, so an ambient `TMPDIR` wins and every worker shares one
directory — which is the matplotlib font-cache race the mechanism exists to
prevent. The witness does not set `TMPDIR` itself: it inherits whatever the
environment has, and sets only `PYTEST_XDIST_WORKER`. So it goes red when
the environment happens to carry a `TMPDIR` — it is **reactive** to the
condition it should be **constructive** about — and it never notices that the
mechanism it watches depends on the environment *not* carrying one.

**How to reproduce:** with `TMPDIR` set, the probe in
`tests/test_parallel_temp_isolation.py` reports the worker's directory as
`TMPDIR` rather than `labcairn-worker-gw0`; without it, the worker gets
`labcairn-worker-gw0`. My first whole-suite run set `TMPDIR` and two of the
five failures were exactly this.

**Also affected:** `tests/evaluation/runner.py:115-118` sets `TEMP`, `TMP`,
`MPLCONFIGDIR` and `LABCAIRN_TEMP_ROOT` for the harness's own subprocess —
**not `TMPDIR`** — so the harness's isolation has the same hole.

**Why CI is unaffected:** `.github/workflows/python.yml` runs `uv run pytest
$files --durations=0` with **no `-n`**, so no xdist worker is ever created
there. This is about local parallel runs and about the harness.

**Recommendation:** set `TMPDIR` alongside `TEMP`/`TMP` in
`conftest.give_this_worker_its_own_temp` and in the harness's runner, and
make the witness set `TMPDIR` itself so the property is watched rather than
assumed.

### F5 — LOW/MEDIUM. The release gate's font check is by file name, and the font audit's own file list includes an extension it does not know

**Where:** `.github/workflows/release.yml:158` (`FONT_SUFFIXES`).

**What is wrong:** the check is
`{".ttf", ".otf", ".ttc", ".pfb", ".pfa", ".afm", ".pfm"}`. The font audit
counts `DarkGarden.sfd` — the font's source, which reportlab ships — among
the seven DarkGarden files, and the release record's §7 names it too. M6b and
M6c (§9) put the GPL v2 font's bytes into the source distribution under
`.sfd` and under `.woff2`, and the gate passed both times.

**How to reproduce:** in a throwaway copy of the tree, commit
`reportlab/fonts/DarkGardenMK.pfb` as `tests/fixtures/papers/fonts/DarkGarden.sfd`,
`uv build`, and run the workflow's own member-list program: **exit 0**, and
the file is in the sdist.

**Recommendation:** add `.sfd`, `.bdf`, `.pcf`, `.woff` and `.woff2` to the
suffix set, or check by content (a font file's own header) rather than by
name. The wheel is unaffected.

### F6 — LOW/MEDIUM. The README's command extraction misses commands outside a shell fence and inside an inline code span, and the two extractors in the gate disagree

**Where:** `tests/test_readme_accuracy.py:64` (`_FENCE_RE`) against
`scripts/outsider_path.py:119` (`fenced_blocks`).

**What is wrong:** M1c, M1d and M1e (§4). A command in a ```console fence is
dropped by **both** extractors and flagged by neither; a command in an
inline code span is dropped by both; and a non-shell fence *between* two
shell fences makes the README gate's extractor mis-pair the fences and read
**prose** as commands. The walk script's extractor pairs fences fence by
fence and its docstring says the pattern-based matcher is the bug to avoid —
**the two extractors in this gate disagree, and the pattern-based one is the
one the README gate uses.**

**How to reproduce:** append a ```console block carrying
`uv run pytest --last-failed` to README.md and run
`pytest tests/test_readme_accuracy.py`.

**Recommendation:** give the README gate the same fence-by-fence pairing the
walk script uses, and read the shell-language set from one place. The
Chinese README's gap (M1b) is already recorded in `CONTRIBUTING.md` §12; the
fence-language gap is not recorded anywhere.

### F7 — LOW. The threat model's enumeration of the writes in `src/` is not watched

**Where:** `docs/THREAT-MODEL.md` §1.2 (the six-row table) against
`tests/test_threat_model.py`.

**What is wrong:** M3b (§6) added a seventh write to `src/labcairn/` and nine
scoped test files stayed green. The C6 witness watches the *property*; no
witness watches the *enumeration*.

**How to reproduce:** add a module under `src/labcairn/` that calls
`Path.write_text`, and run `pytest tests/test_threat_model.py
tests/test_security_paths.py tests/test_workspace_boundaries.py`.

**Recommendation:** a witness that scans `src/labcairn/` for write
primitives and compares the result with the document's table, in the shape
the threat model already uses for its network claim (C13).

### F8 — LOW. The protocol's blocker count is wrong in five shipped documents

**Where:** `docs/EVALUATION.md` lists **six** blockers. *"seven Phase 1
blockers"* appears in five shipped places:
`docs/plans/LC-P1-13-14-task-breakdown.md:50` and `:225`,
`docs/QUICKSTART.md:426`, `docs/RELEASE-NOTES.md:348`, and
`docs/acceptance/LC-P1-14-outsider-path.md:3`.

**What is wrong:** the task breakdown says *"seven"* and then quotes six and
calls them *"the exit test in prose"*. The discrepancy **is recorded** — in
`docs/acceptance/LC-P1-13-evaluation.md` §2 and
`docs/acceptance/LC-P1-13-baseline.md` §7 — but it was never corrected in the
documents themselves, and the harness, which is right, reads six.

**How to reproduce:** `grep -rn "seven Phase 1 blockers" --include=*.md .`

**Recommendation:** five one-word corrections. The protocol is the ruler and
it says six.

### F9 — LOW. A citation in the threat model is outside the watching regex's extension list

**Where:** `tests/test_threat_model.py:93` (`_CITATION`) and
`docs/THREAT-MODEL.md:685` (`pyproject.toml:316`).

**What is wrong:** the regex matches `py|ts|tsx|md|json|html`. The threat
model's 136 `path:line` citations are matched; `pyproject.toml:316` is not.
It resolves today, but a citation to a `.yml`, `.toml`, `.lock` or `.cfg`
file would never be checked.

**Recommendation:** widen the extension list, or say in the document that
only those extensions are cited.

### F10 — LOW. Two in-page anchors cannot resolve, and no test checks any in-page anchor

**Where:** `README.md:174` and `README.zh-CN.md:11`, both
`#许可证状态--尚未授予`; the headings are `### 许可证状态——尚未授予` — two
**EM-dashes** (U+2014) with no spaces, against two **ASCII hyphens**
(U+002D) in the link.

**What is wrong:** no slug rule turns that heading into that anchor. If the
em-dash is preserved the slug carries U+2014; if it is dropped the slug has
no hyphens at all. Either way the link does not resolve. The English
`#licence-status--not-yet-granted` resolves under the drop-the-em-dash rule
and not under the preserve-it rule — I could not settle which GitHub uses,
because this session's web tools were unavailable, so **that half is NOT
MEASURED**.

**Also:** no test in the repository checks any in-page anchor.
`tests/test_readme_accuracy.py::test_readme_names_only_paths_that_exist`,
`tests/test_status_consistency.py::test_relative_links_in_docs_resolve` and
the dossier's link test all skip `#`-only targets.

**Recommendation:** check the anchors, and pick one spelling for the
Chinese heading and its links.

### F11 — LOW. The release notes carry a limitation that was fixed before this commit

**Where:** `docs/RELEASE-NOTES.md` §3.3.

**What is wrong:** it says the two 8.3 short-name witnesses are broken —
*"they reference `RootKind.WORKSPACE`, which does not exist … so they fail
with an `AttributeError` wherever they run"* and *"the property is measured;
the witness is broken."* At this commit both witnesses use `RootKind.OUTPUT`
(`tests/test_security_paths.py:457` and `:490`); the `AttributeError` is
gone. The release notes anchor themselves at `dd08573`, so the sentence was
true there — but the release they describe is `0.1.0`, unreleased, and the
gate commit carries the fixed witness. The record should not tell a reader
that a property is unwatched when it is watched.

**Recommendation:** refresh the limitation when the release notes are
re-anchored, and say the property is watched with the 8.3 fix.

### F12 — LOW. `.env.example` says Phase 1 reads no environment variable, and the provider layer reads one

**Where:** `.env.example` — *"Phase 1 currently reads NO environment variable"* —
against `src/labcairn/providers/credentials.py:254` (`load_credential` reads
`os.environ[settings.credential_env]`).

**What is wrong:** the product reads an environment variable when the
workspace's `providers.json` names one. The `.env.example` sentence is true
of the **default offline run** and false of the product. The repository
knows the nuance —
`docs/acceptance/LC-P1-13-baseline.md` §2.2 says the provider layer *"reads
a workspace's `providers.json` and resolves a credential from an environment
variable name or a file path"* — and the `.env.example` file does not.

**Why it is in scope:** the gate's own reasoning cites `.env.example` as the
reason the real-provider smoke cannot be run. The real reason is the absence
of a credential and of the owner's authorisation, not the absence of an
environment-variable read.

**Recommendation:** reword the sentence to name the default offline run.

### F13 — LOW. The outsider walk's SQLite database reported a disk I/O error under concurrent load on this machine

**Where:** `tests/test_outsider_path.py` in my first whole-suite run.

**What is wrong:** nothing in the product, as far as I can tell. The walk
failed with `sqlite3.OperationalError: disk I/O error`. The failing run had
**two** conditions the passing re-run did not: `TMPDIR` was set (F4), and I
was running a `uv build` and a `uv pip install` into a second virtualenv
against the same volume at the same time. The same sixteen tests **passed in
193.41 s** when re-run alone with neither condition. I did not reproduce the
failure and I did not isolate which of the two conditions caused it, so I
name both rather than pick one. **This is reported as an observation, not as
a finding about the product** — but a gate review that says "the tree is
green" has to say how it knows.

### F14 — LOW. The evaluation report the gate ships asserts that the public fixtures are not in the tree, and they are

**Where:** `tests/evaluation/aggregate.py` — the hard-coded `NOT_MEASURED`
reasons — as they are printed in the report.

**What is wrong:** the report this gate produces, on this tree, says of the
end-to-end-task-success metric:

> *"The public fixtures that would be that corpus are LC-P1-13 T00's
> deliverable and **are not in this tree**."*

`tests/fixtures/public/` holds **four** fixtures, and the same report says so
elsewhere — it lists `test_public_fixtures.py` as a witness. A reader who
takes the reason at its word concludes the corpus is absent.

**This is not a new finding — it is a finding the repository reported and did
not fix.** `docs/acceptance/LC-P1-13-baseline.md` §3.7 says exactly this:
*"Two of the `NOT_MEASURED` reasons are **hard-coded constants** … **Both
statements are false of this tree** … a reader who takes the reason at its
word would conclude the corpus is absent, and it is present and unused."*
The record names the fix as T01's and leaves it undone. **The verdicts are
still right — the reasons are not** — and I have confirmed on this tree that
the reason is still printed.

**How to reproduce:** run `python -m tests.evaluation --out <outside the
repository>` and read the "End-to-end task success" row's reason.

**Recommendation:** make the two reasons read the tree's state rather than
assert a fact about it. This is the fix the baseline record already named.

---

## 12. What I did not test, and why

| What | Why |
|---|---|
| **The real-provider smoke itself.** | There is no credential on this machine and no owner's authorisation to spend money. `docs/EVALUATION.md` requires *"at least one real supported provider under declared model/version/parameters"* and the harness reports the class NOT RUN with the reason and exit code 2. **NOT MEASURED**, and the missing input is named: a provider credential and the owner's authorisation, plus the owner's §1.4.2 decision about which provider. |
| **Any competitor baseline.** | None exists in this tree and none was run. The protocol permits a comparison only like-for-like. **NOT MEASURED**; the missing input is a declared-model run on this side and a second installation. |
| **The four task-level metrics** (end-to-end task success, evidence locator validity by human check, unsupported-claim detection, revision consistency). | The harness reports each as NOT MEASURED with the missing input named: an attempted-task corpus with verified deliveries, a human-checked sample, a no-evidence fixture driven as a task, and a corpus of source-change runs. I did not attempt them. |
| **The release workflow on a GitHub runner.** | The two python programs it carries were extracted from the parsed YAML and run here, and both pass (§9). The shell around them — the `uv` invocations, the pnpm install, the gitleaks download — was not executed, and the workflow has never run on a runner. The release record says the same (§9 of that record). |
| **The Linux and macOS legs of the dependency closure.** | The closure is platform-dependent; I installed and read the **Windows** leg (168 distributions) and the export's marker evaluation (171 requirement lines). The other two platforms were not installed. |
| **`httpx2-jsfetch`**, the one distribution no CI job can install. | Its marker is `sys_platform == 'emscripten'`. It is recorded in the NOTICE; no runner can install it, so no measurement of it is possible here. |
| **Whether GitHub preserves or drops an em-dash in an anchor.** | This session's web tools were unavailable. F10's Chinese-anchor half does not depend on the answer; the English half does. |
| **The web package's own quality gates** (`pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm format:check`). | `web/node_modules` is not installed in my worktree, so the README's `pnpm` rows were skipped by `tests/test_readme_accuracy.py::test_readme_commands_run` — as it reports loudly. **NOT MEASURED**; the missing input is a `pnpm install --frozen-lockfile` in `web/`. |
| **The upstream repositories.** | They are reference material outside this repository, untrusted, and the brief forbids reading `../labcairn-upstreams/`. Every upstream fact in the dossier is checked against `docs/UPSTREAM_REFERENCES.md`, which is in the repository — **not** against the upstream trees. |
| **The POSIX half of the path-guard suite.** | These tests are skipped on this Windows machine, and they run on the other CI runner. **NOT MEASURED**; the missing input is a POSIX runner. |
| **The 8.3 short-name witnesses on a volume that generates short names.** | `E:` does not generate 8.3 names, so `tests/test_security_paths.py:453` and `:486` skip here. I made the short-spelled directory by hand on `C:` to measure the demonstration (§10.3), but I did not re-run those two witnesses under a short-spelled `TMP_PATH` — the mechanism they use builds the short name itself. |

---

## 13. Values I re-measured, and where they now stand

| Value | Where it is recorded | Measured at that commit | Measured at `72154cd` |
|---|---|---|---|
| the Phase 1 blocker count | `docs/EVALUATION.md` | six | **six** — five documents say "seven" (F8) |
| blockers that failed | `LC-P1-13-evaluation.md` §8, `LC-P1-13-baseline.md` §3.4 | two of six | **two of six** in the harness's own run on this tree — the first for the **stale** g1 skip (it holds once that skip is removed) and the second for the POSIX conditional **plus the two 8.3 witnesses** this volume cannot run (F1) |
| the harness's exit code | the evaluation record §1 | 2 | **2** — *"a selected class could not be run"* |
| the gate classes | the evaluation record §3 | Unit 1469/1470, Integration 1131/1134, Negative 361/362, E2E 86/86, Repository gates 305/305 | **Unit 1510/1511, Integration 1131/1134, Negative 361/364, E2E 102/102, Repository gates 369/369**, Real-model smoke **NOT RUN** |
| the corpus exactness metric | the evaluation record §5 | 84/84 — 77/77 — 14/14 | **84/84 — 77/77 — 14/14** — unchanged |
| source-distribution members | `LC-P1-14-release-contents.md` §2.1 | 444 | **452** (the committed tree plus `PKG-INFO`, still exact) |
| wheel members | the same | 153 | **153** — unchanged |
| the dependency closure | the same, and the NOTICE | 171 requirement lines | **171** |
| distributions with a recorded licence | the same | 168 on Windows | **168 on Windows, all sixteen labels, exit 0** |
| matplotlib's font files | the NOTICE §3.1 | 101 | **101** |
| reportlab's font files | the NOTICE §3.2 | 25 | **25** |
| `def test_` definitions / test modules | `docs/REVIEW-DOSSIER.md` §5.3 | 2292 / 106 | **2310 / 108** |
| the dossier's upstream identifiers in `src/` | the same, §4.2 | zero | **zero** |
| `pydantic-ai` import sites | the same, §4.3 | three modules | **three modules, the same lines** |
| `FailureKind`'s members | the same, §4.2 | twelve | **twelve** |
| the threat model's citations | `docs/THREAT-MODEL.md` §7 | — | **136 watched, 1 not** (F9) |
| the dossier's citations | `docs/REVIEW-DOSSIER.md` | — | **61, all watched** |

---

## 14. What I recommend fixing

**I fixed nothing. These are recommendations.**

1. **Correct §1.4.1b before the owner decides** (F1): the second failed
   blocker was the POSIX platform conditional, not the provider-credential
   skip; and the first blocker holds at this commit because the 8.3 defect
   was fixed. **Then take the decision** — my recommendation is Option A for
   the smoke, in Option C's form, with the protocol amended and the
   amendment recorded (§10.5).
2. **Remove the stale skip** in `tests/test_earlier_exit_demos.py`, and
   re-run the harness, so the blocker table describes the tree being handed
   over (F1).
3. **Extend the sixth blocker's witnesses** to look for skipped tests, or
   record the `requires_provider` exclusion explicitly (F2).
4. **Grep the shipped records for the harness's own ranking words** in a
   test of its own (F3).
5. **Set `TMPDIR` as well as `TEMP`/`TMP`** in `conftest.give_this_worker_its_own_temp`
   and in the harness's runner, and make the witness set `TMPDIR` itself
   (F4).
6. **Widen the release gate's font suffix set**, or check by content (F5).
7. **Give the README gate the walk script's fence-by-fence extraction**, and
   read the shell-language set from one place (F6).
8. **Add a witness for the threat model's write enumeration** (F7).
9. **Make the harness's two hard-coded `NOT_MEASURED` reasons read the tree's
   state** (F14) — the fix the baseline record already named and left undone.
10. **Correct "seven Phase 1 blockers" in the five documents** (F8), **widen
    the citation regex's extension list** (F9), **fix the two Chinese
    anchors and check anchors at all** (F10), **refresh the release notes'
    §3.3** (F11), and **reword `.env.example`'s environment-variable
    sentence** (F12).

---

## 15. What this review does not establish

- **It does not close the gate.** The gate's exit test names a real-provider
  smoke that has not run.
- **It does not establish that the whole tree is green on every
  platform.** What it establishes is that on this machine the tree at
  `72154cd` is green: two whole-suite runs — mine (3467 passed, 5 failures,
  each accounted for and each re-run green in isolation) and the harness's
  own (zero failed, zero errored in every class) — agree. The POSIX half of
  the path-guard suite and the two 8.3 witnesses did not run here, and the
  web package's gates did not run at all.
- **It does not review the product.** Another reviewer has the product
  scope. This document covers the records and the package.
- **It does not re-measure the upstream facts**, only their agreement with
  `docs/UPSTREAM_REFERENCES.md`.
- **It does not take the owner's decision** on §1.4.1b. It supplies the
  material and a recommendation, and says plainly that the gate's exit test
  is not met whatever is decided.

---

# 16. The re-verification

**When:** 2026-10-27.
**Tree re-verified:** `8c0eb403c70c161b41a2f8e1407613307a7e6cf9` — the commit
the coordinator named, on the branch `re-verify/g5-records`, in the same
isolated worktree. `git rev-parse HEAD` returned exactly that, and the tree
was clean before and after every mutation below.
**What I changed:** nothing. **I still wrote no fix.** Every change below was
made to break something and then reverted with `git checkout --`, and each
was confirmed reverted with `git status --short` before the next.
**What I did not do:** I did not run the whole suite as a separate step. The
coordinator asked for that, and I ran the **evaluation harness** — which runs
the suite itself — once, alone, after the machine's other harness run had
finished, and I ran the local witnesses one file at a time. The harness's own
report is in §16.3.

## 16.1 The fourteen, one by one

The gate's document numbers my findings **R11–R24** (its own F1–F14). The
column that matters is the third: **does my own mutation now turn it red?**

| # | The finding | My mutation, re-run | Now |
|---|---|---|---|
| **R11** | §1.4.1b misattributes which skip failed which blocker, and the blocker table it cites is stale | the provider-credentials file witnesses **no** blocker; the second blocker's reason was incomplete | **PARTLY** — the task breakdown is corrected; the two acceptance records still carry the old table (**R28**) |
| **R12** | the sixth blocker's "HELD" is not earned | the required tests are read out of the CI's own shard file; a skipped one is named in the blocker's row | **YES** — and the ruling is left to the owner (**§16.2**) |
| **R13** | nothing watches a shipped document for superiority language | the same plain-paragraph section, planted again in `docs/acceptance/LC-P1-13-baseline.md` | **YES** — `test_no_published_record_claims_superiority_over_another_system`, **RED**, the line named |
| **R14** | the parallel-run temp isolation is defeated by `TMPDIR` | an ambient `TMPDIR`, with the worker probe | **PARTLY** — `conftest.py` and the harness's runner are fixed and watched; the walk's own environment is not (**R26**) |
| **R15** | the release gate's font check is by file name | the **real** GPL v2 DarkGarden bytes as `.sfd` and as `.woff2`, in a throwaway copy, a real `uv build`, the workflow's own program | **YES** — **exit 1**, *"carries font files: ['tests/fixtures/papers/fonts/DarkGarden.sfd', 'web/src/assets/labcairn.woff2']"* |
| **R16** | the README's command extraction misses commands outside a shell fence and inside an inline span, and the gate's two extractors disagree | the same three: a `console` fence at the end, a `console` fence in the middle, an inline code span | **YES** — all three **RED**, and the middle one now names the *command*, not prose. There is **one** extractor now, read from the walk script |
| **R17** | the threat model's enumeration of the writes in `src/` is not watched | a seventh write, in a module the list has never heard of | **YES** — `test_the_write_enumeration_in_the_threat_model_matches_the_tree`, **RED** |
| **R18** | the protocol's blocker count is wrong in five shipped documents | `grep -rn "seven Phase 1 blockers"` | **PARTLY** — four of the five now say six; **`docs/QUICKSTART.md` still says seven** (**R27**) |
| **R19** | a citation is outside the watching regex's extension list | `pyproject.toml:316` → `pyproject.toml:9999` | **YES** — **RED**, *"these citations in the threat model do not resolve"* |
| **R20** | two in-page anchors cannot resolve, and no test checks any in-page anchor | the Chinese licence anchor, pointed at a heading that is not there | **YES** — `test_in_page_anchors_resolve`, **RED**, the broken anchor named |
| **R21** | the release notes carry a limitation that was fixed before that commit | read the section | **YES** — it now says the witnesses are **sound** and that they skip only where the volume makes no short names, and it cites this report |
| **R22** | `.env.example` says Phase 1 reads no environment variable | read the file | **YES** — it now says *"Phase 1's **default offline run** reads no environment variable"* and names the provider layer's read |
| **R23** | the walk's database reported a disk I/O error under concurrent load | the walk, alone, with no `TMPDIR` and no concurrent build | **NOT REPRODUCED** — and the `TMPDIR` half of the cause is fixed (R14) |
| **R24** | the evaluation report asserts the public fixtures are not in the tree | the hard-coded reason put back | **YES** — `test_a_not_measured_reason_may_not_contradict_the_tree`, **RED**, *"the reason says the public fixtures are not in the tree, and they are"* |

**Nine fully fixed. Three partly fixed (R11, R14, R18). One not reproduced
(R23).** The three that are partly fixed are the three whose *document* half
was not corrected; in each case the *mechanism* is now watched, and what is
left is a record — which is what §16.4 reports.

## 16.2 R12, judged: does the exclusion record, or does it let anything through?

The coordinator asked me to judge this, so here is the measurement rather
than the description.

**What the fix does.** `tests/evaluation/shards.py::required_test_files`
reads the required tests out of **`.github/ci-shards.json`** — the CI's own
statement of what it runs — so the list cannot drift from the file the CI
runs. `tests/evaluation/aggregate.py::_excluded_required_tests` then names
**every** required test that was skipped, or was not run at all, **with the
test's own reason quoted**, and the sixth blocker's row carries it.

**Three things I measured.**

1. **It is not narrow.** I fabricated a skipped outcome in
   `tests/test_earlier_exit_demos.py` — a required CI test that is not the
   provider-credentials one and that carries no marker — and the sixth
   blocker's row named it, with its reason:

   > `test_earlier_exit_demos.py — 1 case(s) skipped: tests/test_earlier_exit_demos.py::test_a_skipped_case: it did not pass`

   The exclusion does not filter by marker. **Nothing is let through
   silently.**
2. **It is on the page, not only in the model.**
   `test_the_exclusion_is_in_the_rendered_report` **passes**, and the
   rendered row carries the file name.
3. **It does not take the owner's decision.** The blocker's status stays
   **HELD** and the row says, in as many words: *"The exclusion is recorded
   rather than ruled on: whether a declared skip fails this blocker is the
   owner's decision, and this harness does not make it."* That is the other
   of the two options I set out, and the one that does not decide for the
   owner.

**And one thing a reader should know, which is not a defect.** The row lists
every required test the run did not cover. In a **full** run that is a short
list — my own run below lists **seven** — but the harness's `--classes`
option narrows the selection, and in a narrowed run the row carries a list of
every file outside the selection (my probe produced 106 entries). That is
honest, and it is long.

**My judgement: R12 is fixed as designed.** It records the exclusion, it
names the file and the reason, and it leaves the ruling to the owner. What
it does **not** do is make the *status* reflect the exclusion — the status
is still HELD, and the exclusion is visible in the row's prose. That is a
deliberate choice, and the record states it.

## 16.3 The harness's own report on this tree

**The run:** `python -m tests.evaluation --out E:\labcairn-local\tmp-verify-records\evaluation`,
with its own `TEMP`/`TMP`/`MPLCONFIGDIR` under
`E:\labcairn-local\tmp-verify-records`, `TMPDIR` unset, and nothing else
running on the volume. **Exit code 2** — *"a selected class could not be
run"* — after 2399.3 s of measured work.

| The protocol's class | Passed / collected | Skipped |
|---|---:|---:|
| Unit | **1513/1514** | 1 |
| Integration | **1133/1134** | 1 |
| Negative | **363/366** | 3 |
| E2E | **109/109** | **0** |
| **Real-model smoke** | **NOT RUN** — *"no real provider credential is configured in this environment, and the run would spend money"* | — |
| Repository gates | **459/459** | 0 |

**Zero failed and zero errored in every class.** The E2E class — which is
where the outsider's path lives — has **no skip at all**, and the repository
gates are **459/459**. So **R23 did not reproduce**, and the tree at
`8c0eb40` is green on this machine.

**The blocker table, in the harness's own words:**

| The protocol's blocker | Status | What the status means |
|---|---|---|
| New user cannot complete a task from a clean environment following README. | **HELD** | every witness was collected and passed — **0** failing cases |
| Any unauthorized file write/escape or unconsented private-network disclosure. | **FAILED** | **3** of 114 witness cases did not pass — the POSIX-only conditional and the two 8.3 short-name witnesses |
| Fake citation presented as verified or unsupported numerical fact presented as measured. | HELD | every witness was collected and passed |
| A crash silently repeats unknown file side effects. | HELD | every witness was collected and passed |
| Report claims a verified scientific result based solely on schema or rendering checks. | HELD | every witness was collected and passed |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance. | HELD | every witness was collected and passed — **and the row carries the exclusion**, verbatim: *"This run excluded 7 required CI test(s): test_api.py — 1 case(s) skipped …; test_provider_credentials.py — 1 case(s) skipped: … NOT RUN …; test_recovery_support.py — not part of this run; test_security_paths.py — 3 case(s) skipped …; test_skill_ledger.py — not part of this run; … **The exclusion is recorded rather than ruled on: whether a declared skip fails this blocker is the owner's decision, and this harness does not make it.**"* |

**Three things this settles, and one it does not.**

- **The first blocker now holds**, and the gate's own tool says so — the
  stale skip is gone, and the blocker's row says *"every witness was
  collected and passed"*. **R11's substance is confirmed by the tool, not by
  my reading of it.**
- **The second blocker fails for three cases**, which is what the corrected
  §1.4.1b now says. **The record and the tree agree.**
- **The sixth blocker's HELD carries its exclusion**, with the owner's
  ruling left open. **R12 is discharged as designed.**
- **What it does not settle:** whether a declared skip counts. That is still
  the owner's, and the harness now says so in the row a reviewer reads.

**And the metrics.** `unsupported-claim-detection` is now **1/1** — measured
over the public corpus rather than reported NOT MEASURED — and
`recovery-correctness` is **4/4**. The end-to-end reason now reads:

> *"The tree holds the public fixture corpus — **4 fixture(s) and 7
> question(s)** with their answer keys — but a corpus of questions with known
> answers is not a record of deliveries, and nothing in the tree records a
> delivery that was attempted and verified, so the numerator would count
> nothing."*

**"not in this tree" does not appear in the report at all.** R24 is closed.

**And the comparison section still says what it must:**

> *"**No comparison was made, and none is printed.** … no baseline document was
> given, so no comparison was made."*

The report also names the revision it measured and says *"working tree:
clean — the commit is the tree that was measured"*.

## 16.4 What the re-verification found that the first review did not

### R25 — LOW. The shipped-record superiority watch's unit is a line, and a line break defeats it

**Where:** `tests/test_evaluation_harness.py::test_no_published_record_claims_superiority_over_another_system`,
and the patterns it uses (`tests/evaluation/report.py::ranking_pattern` and
`::target_pattern`).

**What is wrong.** The watch's unit is a line: a line that carries a verdict
word **and** names one of the systems the protocol lists is a claim. A
superiority claim whose verdict word and whose named system fall on
**different lines** is therefore not seen. I planted, in a plain paragraph of
`docs/QUICKSTART.md`:

> LabCairn outperforms the other
> system, PaperQA2, on citation support.

— and the watch stayed **green**. Two other shapes are caught, so the seam is
narrow and specific: the name on the **same** line, before the verdict word,
is caught; the name on the same line inside a **code span** is caught; only
the **line break** between them escapes.

**Why it matters, and how much.** The repository wraps prose at about 79
columns, so a line break at the wrong place is a thing that happens. The
witness's own docstring names one limit — *"A record that dressed a
superiority claim as a block quote would pass here"* — and says plainly that
it is *"a real one"*. **The line-wrap limit is not named.** That is the
difference between a stated limit and an unstated one, and it is the only
thing wrong with an otherwise careful witness.

**Recommendation:** either join the line before the pattern runs, or name the
limit in the witness's docstring, the way the block-quote limit is named.

### R26 — LOW/MEDIUM. The walk's own environment still does not set `TMPDIR`

**Where:** `scripts/outsider_path.py::child_environment` (the function at
the tree at `8c0eb40` sets `TEMP`, `TMP` and `MPLCONFIGDIR`, and its own
docstring says *"The temporary directory is outside the repository, and it is
the script's own: `TEMP`, `TMP` and `MPLCONFIGDIR` all point inside the
run's work root"*).

**What is wrong.** `grep -c TMPDIR scripts/outsider_path.py` is **zero** on
this tree. The gate's review record says R14 was fixed *"in the conftest, in
the harness's runner, and in the outsider's own environment"* — **the third
of those three is not fixed at this commit**, and I measured it rather than
reading it:

| | the walk's environment | a child of the walk gets |
|---|---|---|
| no ambient `TMPDIR` | `TEMP`/`TMP` → the walk's own `tmp`, `MPLCONFIGDIR` → its `matplotlib` | **the walk's own `tmp`** |
| an ambient `TMPDIR` | `TEMP`/`TMP` → the walk's own `tmp`, `TMPDIR` → **not set**, so the ambient one passes through | **the ambient directory** |

So the walk's isolation claim is false on a machine that carries a `TMPDIR`,
and the walk's children — including the `uv run pytest` it runs in the clone
— would share that directory with whatever else uses it. **No test watches
this function**: `grep -rn TMPDIR tests/test_outsider_path.py` is empty, and
`child_environment` is called from the script alone.

**Recommendation:** set `TMPDIR` in `child_environment` as the other two
mechanisms now do, and give the walk's environment a witness of its own.

### R27 — LOW. The protocol's blocker count is still "seven" in the quickstart, and a record says the wrong number is gone

**Where:** `docs/QUICKSTART.md:426`, and
`docs/acceptance/LC-P1-13-evaluation.md:97-104`.

**What is wrong.** Four of the five documents that repeated the wrong number
now say six — the task breakdown (twice), the release notes and the
outsider-path record. **The fifth, the quickstart, still says seven.** And
the evaluation record now says:

> *"The discrepancy was recorded rather than resolved, and this gate's own
> review found it again; the five shipped documents that repeated the wrong
> number now say six, and **the wrong number is gone**."*

That is **false of this tree**: `grep -rn "seven Phase 1 blockers" --include=*.md .`
returns the quickstart's line, beside the two places where the phrase is
being *discussed*.

**Why it matters.** A record that says a correction is done when it is not
is the same shape as R11 — and the repository's own rule says the
measurement wins and the record is corrected.

### R28 — LOW/MEDIUM. The blocker table itself was corrected in one document and not in the two that carry it

**Where:** `docs/acceptance/LC-P1-13-evaluation.md` §8 and
`docs/acceptance/LC-P1-13-baseline.md` §3.4 and §3.6 — neither of which
changed at all between `72154cd` and `8c0eb40`.

**What is wrong.** The task breakdown's §1.4.1b is now correct: it says
**one** of the six did not hold, it attributes it to the second blocker with
its three skipped witness cases, and it records that the first blocker's skip
was removed. **The two acceptance records that carry the table still carry
the old one.** The evaluation record's §8 still says:

> *| New user cannot complete a task from a clean environment following README.
> | **FAILED** | 4 | 2 of 51 witness cases did not pass …|*

and the baseline record §3.6 still says:

> *"**The blockers, on this tree: two of the six FAILED, four HELD** — the same
> two as the recorded run and for the same reasons"*, and §3.3 of that record
> says the finding is *"current rather than historical"*.

The tree has moved: my own run of the harness on it says **one** of the six
failed and the first blocker **holds**; and the second blocker's failing
witness cases are **three** on a volume without 8.3 names, not one. **The
evaluation record's own table is anchored to `37ae366` and says so at the
top**, so a stale table is not a lie in itself — but the baseline record's
§3.6 is headed *"A fresh measurement on this tree"* and now describes a tree
that is not this one.

**Recommendation:** re-measure the blocker table on the tree the gate closes
on and put it in both records, or move the dated table into a dated section
and say which tree it describes.

## 16.5 The re-verification's verdict

**PASS WITH NOTES** for the scope I re-verified — the same scope, the same
vocabulary, and **this verdict closes nothing either**.

**In one sentence:** every one of my fourteen findings was re-tested by
re-running my own mutation, **nine are now watched and hold, three are
watched but their document half was not corrected, one was not reproduced** —
and the re-verification itself found **four new items**: an unstated limit in
the new superiority watch, a walk environment the gate record says was fixed
and is not, a quickstart that still says "seven", and two acceptance records
whose blocker table describes a tree that is not this one.

**What has to happen before the gate closes**, beyond the owner's four
decisions:

1. **R26** — set `TMPDIR` in `scripts/outsider_path.py::child_environment`,
   and give it a witness. The gate record currently says this was done.
2. **R27** — correct `docs/QUICKSTART.md:426`, and correct the evaluation
   record's claim that the wrong number is gone.
3. **R28** — re-measure the blocker table on the tree the gate closes on and
   put it in both acceptance records.
4. **R25** — name the line-wrap limit in the new witness's docstring, or
   close it.

**And the owner's open decisions are unchanged by this re-verification.**
§1.4.1b now asks the right question — the second blocker's platform
conditional, not the provider-credential skip — and the harness still leaves
the ruling to the owner. **The gate's exit test names a real-provider smoke
that has not run, and nothing in this re-verification changes that.**

---

# 17. The final re-verification

**When:** 2026-10-27.
**Tree re-verified:** `042cf76c098c02975f7b535de2af3e1ed8591b6d` — the commit
the coordinator named, on the branch `re-verify/g5-records-final`, in the same
isolated worktree. `git rev-parse HEAD` returned exactly that, and the tree
was clean before and after every mutation below.
**What I changed:** nothing. **I still wrote no fix.** Every change below was
made to break something and then reverted with `git checkout --`, and each
was confirmed reverted with `git status --short` before the next.
**What I ran:** the local witnesses for each finding, one file at a time. I did
**not** run the whole suite and I did **not** run the harness again — the
coordinator's own harness report on `c362317` is on disk
(`E:\labcairn-local\harness-final2\evaluation-report.md`), and I read it
against the records rather than paying for a second run. The base temp
directory was `E:\labcairn-local\bt-verify-final` and each process had its own
`TEMP`/`TMP`/`MPLCONFIGDIR` under `E:\labcairn-local\tmp-verify-final`, with
`TMPDIR` unset.

## 17.1 The four, one by one

| # | The finding | My mutation, re-run | Now |
|---|---|---|---|
| **R26** | the walk's own environment still does not set `TMPDIR` | the `environment["TMPDIR"] = str(tmp)` line **removed** from `scripts/outsider_path.py::child_environment` | **CLOSED** — `tests/test_outsider_path.py::test_the_walk_hands_its_children_a_temporary_directory_of_its_own` **RED**: *"the walk hands its children TMPDIR='…\\ambient', and the ambient one it was supposed to replace is …"* |
| **R25** | the shipped-record superiority watch's unit is a line, and a line break defeats it | the same cross-line claim, planted again in a plain paragraph of `docs/QUICKSTART.md` | **HALF CLOSED** — the wrap no longer hides it (**RED**, and the message shows the joined paragraph); **but the negation half of the fix does not run** (**R30**) |
| **R27** | the quickstart still said seven, and a record said the wrong number is gone | `grep -rn "seven Phase 1 blockers"` | **CLOSED** — the quickstart says *"the six Phase 1 blockers"*, and the only surviving occurrence of the phrase is the evaluation record **discussing** it. The record's sentence — *"the five shipped documents that repeated the wrong number now say six, and the wrong number is gone"* — **is true now**, and I checked all five: the task breakdown twice, the release notes, the outsider-path record and the quickstart |
| **R28** | the blocker table was corrected in one document and not in the two that carry it | the coordinator's harness report on `c362317`, read against both records' new tables | **HALF CLOSED** — the table is in both records and the **statuses are right**; **but the records' narrative still contradicts their own table**, and one cell is stale (**R31**) |

**Two closed, two half closed.** And the half-closed ones are not a
half-measure of the same thing: one is a **witness that does not do what the
gate record says it does**, and the other is **two shipped records that state
things false about the tree**.

## 17.2 R25, re-run: the wrap is closed, and the negation is not

**The wrap.** My mutation — a plain paragraph in `docs/QUICKSTART.md` whose
verdict word and named system fall on different lines — is now **RED**:

> `docs\QUICKSTART.md:430: LabCairn outperforms the other system, PaperQA2, on citation support.`

The message shows the **joined paragraph**, so a wrap no longer hides a
claim. **That half of R25 is closed.**

**The negation, and the two controls.** The fix also splits a paragraph into
sentences and recognises a denial. The coordinator asked me to run the two
denied sentences from the dossier as controls, and to run the cross-line
claim; here is what I measured.

- **the control** — the dossier's own sentence, planted as a plain
  paragraph:

  > it contains no claim that LabCairn is better than any upstream project

  **not caught** ✓
- **the control** — the protocol's own ban, planted as a plain paragraph:

  > forbids claiming superiority over PaperQA2/PaperSpine/others

  **not caught** ✓
- **the claim** — the cross-line superiority claim — **caught** ✓

**But the controls are not caught by the negation.** I neutralised the
negation check — the one line that exempts a denied sentence — and re-ran
the witness on the same two controls: **still green, unchanged**. So the
negation path is not what protects them.

**Why they are protected, measured.** The watch's two lists, read out of the
protocol's own clause:

- the first sentence carries a verdict word but names **no target**. The
  targets are `('PaperQA2', 'PaperSpine')`, and neither *"LabCairn"* nor
  *"any upstream project"* is among them;

- the second carries the targets but its verdict word is *"superiority"*,
  and the ranking pattern is `\b(better|worse|best|worst|superior|outperform|beats|winner|loses|ahead)(?:s|es|ed|ing|er|ers)?\b` — which does **not** match *"superiority"*.

**So the two controls pass by vocabulary, not by negation.** The negation is
supposed to be the mechanism, and it is not.

## 17.3 R30 — NEW. The negation exemption never fires, and it produces a false positive

**Where:** `tests/test_evaluation_harness.py:1700-1703`, the `_NEGATION`
pattern.

**What is wrong.** The pattern's bytes are:

```python
_NEGATION = re.compile(
    r"\x08(?:not|no|never|without|forbid|forbids|forbidden|cannot|neither|nor|"
    r"refuse|refuses|prohibit|prohibits)\x08",
    re.IGNORECASE,
)
```

**The two `\b` were written as raw backspace bytes (0x08)**, not as the two
characters `\` and `b`. So the pattern asks for a **literal backspace
character** on each side of the negation word, and prose never contains one.
**The negation exemption can never match anything.**

I asked the witness's own machinery directly. Five denied sentences, each
planted in a paragraph of its own:

> LabCairn does not outperform PaperQA2 on citation support.

> This document contains no claim that LabCairn beats PaperQA2.

> The protocol forbids claiming superiority over PaperQA2.

> No winner was declared against PaperSpine.

> LabCairn never outperformed PaperQA2.

**None of them matches `_NEGATION`.** The intended pattern, with a real
word boundary, matches **every one of the five**.

**Two consequences, both measured.**

1. **A false positive.** The sentence

   > LabCairn does not outperform PaperQA2 on citation support.

   — a **denial** — is **flagged as a superiority claim** (my mutation F:
   **RED**), with and without the negation check. So a shipped record that
   correctly *denies* a comparison is reported as making one. **That is the
   opposite of what the fix's own docstring says**: *"a sentence that denies
   one thing and then claims another … is let through. It is stated here
   rather than left for a reader to discover."*
   **And it is not theoretical: this report was flagged while this section
   was being written**, for the sentences it quotes — and had to be reworded
   before it could be committed.
   In fact **every** denial is let through nowhere — none is exempt.
2. **The negation path has no witness.** Neutralising the negation check
   changes nothing about the tree's verdict, which is exactly what a dead
   mechanism looks like from the outside.

**And the gate record's table states it is fixed.** `docs/acceptance/G5-acceptance.md`
says of R25: *"yes — the unit is the **paragraph, joined**, so a wrap cannot
hide a claim, and a sentence that **denies** is not a claim: the review
dossier's own … is what the first attempt called a claim."* **The first half
is true and the second half is not.** The dossier's sentence is not called a
claim — but not because a denial is recognised.

**Recommendation.** Write the two characters `\` and `b` where the backspace
bytes are, and add a witness of the form: a denied superiority claim, with a
verdict word and a named target, is **not** reported — and the control that
neutralising the negation makes it reported.

## 17.4 R28, re-run: the table is in both records, and the narrative is not

**What is right.** Both records now carry the re-measured table, and I
checked every row against **the coordinator's own harness report on
`c362317`** (`E:\labcairn-local\harness-final2\evaluation-report.md`,
revision `c36231703aded75b…`, exit code 2):

| The protocol's blocker | The harness on `c362317` | Both records' new tables |
|---|---|---|
| New user cannot complete a task from a clean environment following README. | **HELD**, 4 witnesses, 0 failing cases | **HELD** ✓ |
| Any unauthorized file write/escape or unconsented private-network disclosure. | **FAILED**, 4 witnesses, **3 of 114** witness cases did not pass | **FAILED**, *"3 of 114 … all three are skips"* ✓ |
| Fake citation presented as verified or unsupported numerical fact presented as measured. | **HELD**, 4 witnesses | **HELD** ✓ |
| A crash silently repeats unknown file side effects. | **HELD**, **4** witnesses | **HELD**, **3** witnesses ✗ |
| Report claims a verified scientific result based solely on schema or rendering checks. | **HELD**, 3 witnesses | **HELD** ✓ |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance. | **HELD**, 3 witnesses, **and the row names the seven excluded required CI tests with their reasons**, ending *"The exclusion is recorded rather than ruled on: whether a declared skip fails this blocker is the owner's decision, and this harness does not make it."* | **HELD**, *"every witness passed, **and the row names the excluded required tests with their reasons** — whether a declared skip fails this blocker is the owner's ruling, not the harness's"* ✓ |

**Five of the six rows match, including the sixth — which is the row the
coordinator asked me to check, and it is right.** The statuses, the counts of
failing cases, and the exclusion's wording all agree with the harness's own
report.

## 17.5 R31 — NEW. The records' narrative still contradicts their own table

**Where:** `docs/acceptance/LC-P1-13-evaluation.md` §2 and
`docs/acceptance/LC-P1-13-baseline.md` §3.3, §3.4 and §3.6.

**What is wrong.** The tables were added; the sentences around them were not
corrected, and in one place the edit made a stale statement *newly* false.

**The evaluation record's headline, §2, item 2 — now:**

> **One of the six Phase 1 blockers did not hold.** The one — *"A new user
> cannot complete a task from a clean environment following README"* — because
> the base branch's own witness skips G1's exit demonstration on Windows while
> the product's 8.3 short-name comparison is unfixed.

**That names the wrong blocker and a reason that no longer holds.** The
record's own new table says the clean-environment blocker **HELD**, and the
unauthorised-write blocker **FAILED**; the harness on `c362317` says the same;
and the 8.3 comparison **was** fixed (`6220a08`) and its skip removed
(`f708076`). The edit changed *"Two of the six"* to *"One of the six"* and
left the rest of the sentence pointing at the old blocker — which is the very
misattribution R11 was about, **in the record that reports R11**.

**The baseline record's §3.3, §3.4 and §3.6 still say:**

> *"the recorded run reports two of the six blockers as FAILED for exactly
> that reason"* · *"**§3.6 is the same table measured on this tree** … **the
> two blockers that failed are the same two, for the same reasons**"* ·
> *"**§3.6 measured the same two as FAILED on this tree, with the same witness
> cases**, so the finding is **current rather than historical**"*.

Every one of those is false of this tree, and each contradicts the new table
**in the same document**.

**And one stale cell.** The records' table says the crash blocker has
**3** witnesses; the harness on `c362317` says **4**, and the manifest at
this commit agrees — `test_fault_injection_e2e.py` was added to
`no-repeated-side-effect-after-crash`
(`tests/evaluation/manifest.py:381-386`).

**Recommendation.** In the evaluation record's §2, name the blocker that
actually failed and drop the reason that was fixed; in the baseline record's
§3.3–§3.6, say which tree each table describes and stop calling the old one
current; and correct the crash blocker's witness count in both tables.

## 17.6 R32 — NEW. The sentence split opens a seam of its own

**Where:** `tests/test_evaluation_harness.py::test_no_published_record_claims_superiority_over_another_system`,
and the `_sentences` helper it uses.

**What is wrong.** The watch's unit is now the **paragraph, joined**, and each
paragraph is split into sentences; a sentence is a claim when it carries both a
verdict word and a named target. So a superiority claim whose **verdict word
and named system fall into different sentences of the same paragraph** is not
seen. I planted, in a plain paragraph of `docs/QUICKSTART.md`:

> PaperQA2 is one of the systems this project is compared with. LabCairn
> outperforms it on citation support.

— and the watch stayed **green**. The machinery says why: the first sentence
has the target and no verdict word, the second has the verdict word and no
target, and neither has both.

**Why it matters, and how much.** It is the mirror of the seam R25 was about,
opened by the fix that closed it: the line-wrap became a sentence-wrap. It is
narrow — it needs the claim split across two sentences of one paragraph — and
the witness's docstring names **one** limit (*"a sentence that denies one
thing and then claims another"*) but **not** this one.

**Recommendation.** Judge the **paragraph** against the vocabulary, and use
the sentence split only for the negation, so that a target in one sentence
and a verdict word in the next still counts.

## 17.7 The final verdict

**BLOCKED** — and the block is on the **closure**, not on this scope's own
claims.

**In one sentence:** two of the four findings are closed and two are half
closed; one of the half-closed ones is a **witness whose stated criterion is
not implemented and which reports a denied superiority claim as a claim**,
and the other is **two shipped acceptance records that state things false
about the tree** — and the gate record's table says all four are fixed.

**What holds.** Everything this scope is about holds, and is witnessed:

- the **release contents** are right when the artefacts are built and checked;
- the **dossier's** references resolve and its independence claims are
  earned from the tree;
- the **baseline** invents no superiority, and the report's comparison section
  still says *"No comparison was made, and none is printed"*;
- the **quickstart's** artefact facts are true of the code, measured by
  running the CLI and by hashing bytes;
- the **threat model's** 136 watched citations resolve and its write
  enumeration is now watched too;
- the **protocol's blocker count** is right in all five documents that
  repeated it;
- and the **owner's** §1.4.1b decision is now asked the right question, with
  the harness's own report saying *"The exclusion is recorded rather than
  ruled on: whether a declared skip fails this blocker is the owner's
  decision, and this harness does not make it."*

**What does not hold, and is open:**

1. **R30 — the negation exemption never fires.** `_NEGATION` carries raw
   backspace bytes where the word boundaries were meant, so a denied
   superiority claim is reported as a claim, and the negation path has no
   witness. The gate record says this half of R25 is fixed; it is not.
2. **R31 — two acceptance records state things false about the tree.** The
   evaluation record's headline names the wrong blocker with a fixed defect as
   its reason, and the baseline record still calls its old table *"current
   rather than historical"*. The gate record says R28 is fixed; the table is
   there, but the records still contradict it.
3. **R32 — the sentence split opens a seam** the paragraph join closed, and
   the witness's docstring does not name it.

**What I recommend before the gate closes:** fix the two bytes in `_NEGATION`
and give the negation path a witness; correct the evaluation record's
headline and the baseline record's §3.3–§3.6, and the crash blocker's
witness count in both tables; and either close the sentence seam or name it.
**None of the three touches the product, the release contents, or the
owner's decisions** — they are a witness's regex, two records' sentences,
and one seam.

**And the owner's decisions are unchanged.** The gate's exit test names a
real-provider smoke that has not run, and nothing in this re-verification
changes that.

---

# 18. The fixes, re-verified

**When:** 2026-10-27.
**Tree re-verified:** `09ac9b7839266b183c8dcf9ad3eb1ccb009a80ea` — the commit
that answers §17, on `delivery/g5`, in `E:\LabCairn`. `git rev-parse HEAD`
returned exactly that, and the tree was clean before and after every mutation
below.
**What I changed:** the corrections this re-verification itself produced — one
cell and one header in `docs/acceptance/LC-P1-13-evaluation.md` (§18.4), and two
docstrings in `tests/test_evaluation_harness.py` (§18.5). **No product code, no
shard file, no gate record.**
**What I ran:** the superiority watch, one mutation at a time, each planted as a
plain paragraph at the end of `docs/QUICKSTART.md` and reverted with
`git checkout --`, with `git status --short` read between mutations; then the
whole `tests/test_evaluation_harness.py` and `tests/test_status_consistency.py`
on this tree; and `ruff check` and `ruff format --check` on the file I touched.
The base temp directory was `E:\labcairn-local\bt-rv-*`; `TEMP`, `TMP` and
`MPLCONFIGDIR` were under `E:\labcairn-local\tmp-rv` and `TMPDIR` was unset.
**I did not run the harness itself** — §17's reading of the `c362317` report is
the measurement, and I read the records against it rather than paying for a
second run.

## 18.1 The three, one by one

| # | The finding | My mutation, re-run | Now |
|---|---|---|---|
| **R30** | the exemption's boundaries were raw backspace bytes, so a denial was reported as a claim, and the exemption had no witness | (a) a denied claim, planted as a plain paragraph; (b) the same paragraph with the exemption neutralised | **CLOSED** — (a) **green**, the denial is not reported; (b) **RED** on the planted paragraph **and on `docs/REVIEW-DOSSIER.md:16`**, whose paragraph needs the exemption — so the mechanism is not dead and cannot be neutered silently |
| **R31** | the records' prose contradicted their own table, and one cell was stale | the `c362317` report and the manifests at each run's commit, read against all three tables | **CLOSED, with one correction** — the prose now says which run it describes, both current tables say four, and **the historical table's count, which this fix had changed to four, is corrected back to the three its own run measured** (§18.4) |
| **R32** | the sentence split let a claim whose target and verdict word fell in different sentences | the same claim, planted as one paragraph; and a cross-line claim, planted again | **CLOSED** — both **RED**, and the message shows the joined paragraph |

## 18.2 R30 — the bytes are characters again, and the exemption is load-bearing

**The bytes.** `tests/test_evaluation_harness.py` holds **zero** `0x08` bytes,
and the pattern now carries the two characters `\` and `b`:

```python
_NEGATION = re.compile(
    r"\b(?:not|no|never|without|forbid|forbids|forbidden|cannot|neither|nor|"
    r"refuse|refuses|prohibit|prohibits)\b",
    re.IGNORECASE,
)
```

**The false positive is gone.** A denied claim, planted as a plain paragraph:

> LabCairn does not outperform PaperQA2 on citation support.

— is **not reported**. On `042cf76` this was the reviewer's mutation F, and it
was red.

**The exemption is load-bearing, and that is measured rather than asserted.** I
planted the same paragraph again and neutralised the exemption with
`_NEGATION = re.compile(r"(?!)")`. The watch went **RED**, and the offenders
were the planted paragraph **and `docs/REVIEW-DOSSIER.md:16`**:

> **What this document is not.** It is not a comparison, and it contains no
> claim that LabCairn is better than any upstream project.
> `docs/EVALUATION.md:29` forbids claiming superiority over
> PaperQA2/PaperSpine/others without like-for-like matched-task baselines …

**That is the one sentence in the tree whose exemption the dossier needs.** §17
measured the two controls passing by vocabulary when the unit was the sentence;
at the paragraph, the dossier's paragraph carries both lists in one paragraph,
and only the exemption keeps it from being reported. **So the exemption cannot
be neutered silently**, which is what §17's R30 said about it. It is not a
planted control — a planted one would be stronger, and that is a note rather
than a block — but it is a witness the tree already had.

**The limit, at the paragraph and measured.** The exemption's unit is the
paragraph, so a negation anywhere in it exempts every claim it carries. A
paragraph planted as:

> There is no like-for-like baseline in this document. LabCairn outperforms
> PaperQA2 on citation support.

— stayed **green**. That is the mirror of the *"not A, but better than B"* limit
the docstring already named, and it is now stated at the unit the code uses
(§18.5).

## 18.3 R32 — one unit for all three tests

**The seam is closed.** The claim §17 planted across two sentences of one
paragraph:

> PaperQA2 is one of the systems this project is compared with. LabCairn
> outperforms it on citation support.

— is **RED**, and the message shows the **joined paragraph**, so the split no
longer hides it.

**And R25's closer is still closed.** The claim wrapped across two lines:

> LabCairn outperforms the other system, PaperQA2,
> on citation support.

— is **RED** too, with the lines joined in the message. The ranking word, the
named target and the exemption are judged on **one** unit now, and that is what
makes both seams shut.

## 18.4 R31 — the prose, the tables, and the cell the fix broke

**The prose.** The evaluation record's §2 now says *"did not hold, in that
run"* and points at the table the gate closes on; its note says the defect was
fixed and the skip removed. I checked both: `6220a08` is the 8.3 comparison,
`f708076` is the skip's removal, and `tests/test_earlier_exit_demos.py` no
longer skips on Windows — it says the skip is gone, and why. The `c362317`
report says the clean-environment blocker **HELD**, so the note is true of this
tree.

**The baseline's narrative.** §3.3 now calls the recorded run *historical, not
current*; §3.4's finding is *historical rather than current*; and §3.6 names its
tree (`977a19b`) and its own run. At `977a19b` the two blockers did FAIL — the
8.3 skip is still there at that commit — so the historical sentences are true of
the tree §3.6 anchors.

**Both current tables say four, and four is what was measured.** The `c362317`
report says **4** witnesses for the crash blocker, and the manifest at
`c362317` lists four files; the fourth, `test_fault_injection_e2e.py`, arrived
in `86fce86`.

**The cell the fix broke.** `docs/acceptance/LC-P1-13-evaluation.md` carries two
tables: the document's own run at `37ae366`, and the table re-measured at
`c362317`. The fix changed the crash count to **4 in both**, but the `37ae366`
run measured **3**: the T01 report on disk
(`E:\labcairn-local\evaluation-t01\evaluation-report.md`, revision `37ae366…`)
says *"A crash silently repeats unknown file side effects. | HELD | 3"*, and the
manifest at `37ae366` lists three files. **A historical table was made to state
a number its own run did not measure** — the same class of error R31 was about,
one table over. I corrected the cell back to **3**, and the header now reads
*"Status at `37ae366`"*, so each table names its tree the way §16 asked.

## 18.5 The two docstrings the fix left describing a unit it had removed

The test's own docstring still said *"**The unit is a line** …"*, and the
exemption's comment still said *"A **sentence** that denies …"* — both describe
units the code no longer uses. The line wording arrived with `86fce86`, so it
was inherited rather than introduced here; the fix removed the sentence split
and left the sentence behind. Both now say **paragraph**, and the limitation
§18.2 measured is written at that unit. **A witness that describes a unit it
does not use is a claim about the tree that the tree does not hold**, which is
the finding R31 was about.

## 18.6 The final verdict

**PASS WITH NOTES** for the scope §17 blocked on — and **this verdict closes
nothing either**.

**In one sentence:** all three findings are **closed by measurement**; the
re-verification found **two false statements the fix left standing** — a
historical table carrying a count its run did not measure, and two docstrings
describing a unit the code had removed — and both are corrected in this commit.

**What holds, and is witnessed on this tree:**

- a denied claim is not reported, and neutralising the exemption reddens the
  tree, so the negation path is alive and watched;
- a claim split across sentences or across lines of one paragraph is reported,
  with the joined paragraph in the message;
- the records' prose and both current tables agree with the `c362317` report,
  and each table now names the commit it describes;
- and the tree is otherwise unchanged: **248 passed** across
  `tests/test_evaluation_harness.py` and `tests/test_status_consistency.py`,
  `ruff check` and `ruff format --check` clean.

**Notes, and they are notes rather than blocks:**

1. **The exemption's unit is the paragraph**, so a negation anywhere in a
   paragraph exempts every claim in it. It is measured (§18.2) and now documented at that
   unit; tightening it would mean judging the claim sentence by sentence, which
   is the seam R32 closed.
2. **The exemption's witness is the dossier's own paragraph**, not a planted
   control. That is what makes it a witness the tree cannot lose silently; a
   planted control would be the stronger arrangement, and it is not in this
   commit.
3. **The owner's decisions are unchanged.** The gate's exit test names a
   real-provider smoke that has not run, and nothing in this re-verification
   changes that.
