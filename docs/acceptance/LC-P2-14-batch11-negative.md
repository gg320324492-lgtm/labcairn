# LC-P2-14 — Batch 11: three honest refusals — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) ·
**Routes watched:** [LC-P2-07](LC-P2-07-fidelity-baseline.md) (OOXML reader and
material ingestion), [LC-P2-08](LC-P2-08-acceptance.md) (content identity and the
version graph), and the CEJ negative witnesses in
[`LC-P2-14-cej-pilot.md`](LC-P2-14-cej-pilot.md) §2.

**Status.** Three synthetic negative witnesses are in one existing test file and
mutation-checked. The reconnaissance that named the three structural classes is
chain-external at `E:\labcairn-local\batch11-recon\RECON.md` §3 and §5. Its
material was read only; this record and every fixture carry **no manuscript
sentence, comment text, author name, paper title, directory label, or real file
name**. Only counts, structural labels, synthetic bytes and neutral labels appear
here. No product source file, real pilot store, CI run, push or pull request is
part of this work.

**Measured:** 2026-11-05, Windows 11 (AMD64), Python 3.12, in a git worktree
whose `main` was `00e675864a1a1d1a98605338b7f6a75253685ace`. `PYTHONPATH` pointed
at this worktree's `src`. Every pytest basetemp, and all four temp variables
(`TEMP`, `TMP`, `TMPDIR`, `MPLCONFIGDIR`), were outside the repository and
distinct per run. No whole-suite pytest run was performed.

---

## 1. What batch 11 made necessary

| Structural class (chain-external count) | The guess a product must not make |
|---|---|
| 88 readable `.docx`; 15,080 red runs; 1,479 `w:ins` and 639 `w:del` across the batch; marked/clean pairs use red `EE0000` font while most marked files have no tracked changes | A `w:color` value is formatting. It is not a `w:ins`/`w:del` element and must not mint a `RevisionEvent`. |
| 3 empty-text graphical containers; their normalized `w:t` text hash is `sha256("")`, while 3 embedded images and 3 raw file hashes differ | Equal body-text hashes are not equal content. Two image-only containers must not be merged into one file or one version. |
| 1 marked/clean pair has zero red runs and zero tracked changes on both sides; 4 `comments.xml` parts hold only 2 non-empty comment sets | A display name claiming marked changes is not a semantic event. Neither a revision nor a comment may be inferred from the name. |

The CEJ record already carries a general negative witness with `FF0000`. The
first witness below does not duplicate it: it pins the second observed colour
value, `EE0000`, and re-measures the CEJ witness with a cross-mutation. The
other two properties had no witness and are new.

## 2. The witnesses and their contracts

| # | Property | Witness | Contract |
|---|---|---|---|
| 1 | `EE0000` and `FF0000` are formatting, not tracked changes | `tests/test_ooxml_revisions.py::test_ee0000_and_ff0000_are_formatting_not_tracked_revisions` | A synthetic package has two ordinary runs, one per colour value, and no `w:ins`, `w:del`, move, row mark, comment or problem. Both views keep the two clauses once; `revisions`, `comments` and `problems` are empty. |
| 2 | Empty body text does not merge two image containers | `tests/test_ooxml_revisions.py::test_two_empty_text_image_containers_are_not_one_version` | Two synthetic OOXML packages have one paragraph with a drawing and no `w:t`; the two image parts differ. Each ingestion produces one empty text unit whose text hash is `sha256("")`, while the two raw SHA-256 values, source ids and byte-level `VersionSummary` digests are distinct. A deliberately text-hash-only pair is shown to be reported as one duplicate by `check_duplicates`; the byte-level pair is not. |
| 3 | A marked-changes name does not mint an event | `tests/test_ooxml_revisions.py::test_a_marked_changes_filename_mints_no_revision_event` | A neutral synthetic filename contains the phrase "with marked changes"; the package has no red run, tracked change, move, comment or problem. The reader reports zero events, the DOCX adapter emits exactly one body-text unit, and ingestion emits no problem and exactly one text unit. |

All three witnesses were appended to `tests/test_ooxml_revisions.py`. No new test
file was added, so no shard-list or evaluation-manifest registration was needed;
`tests/test_ci_shard_coverage.py` was re-run and stayed green. The synthetic
packages are built in memory from neutral XML and byte strings. No fixture file
is written to the repository or to a real pilot store.

## 3. Mutations: each witness fails for its own property

The harness and its byte-for-byte backups live outside the repository at
`E:\labcairn-local\batch11-negative\`. It applies one mutation to one product
file, runs the three new witnesses plus the CEJ red-font witness, restores the
original bytes, verifies SHA-256, and runs the four witnesses again. It uses
`read_bytes`/`write_bytes`, never `git checkout --`, and deletes no assertion.
The two product files' original SHA-256 values were:

```
ooxml.py  954e6825cbf7693d7cf72239f3bcd0c35cf7fdbc55eaddfcf0a2693de6fb105a
ingest.py 9712c6e3d7b3247e03790560e8bee5a8b0f74f24bc4a60c695a2b6f3379267cf
```

| Mutation | Product shortcut it introduces | Red / green |
|---|---|---|
| `ee0000-only` | treat a run with `w:color@w:val="EE0000"` as an insertion | Property 1 **FAILED** on `document.revisions == ()`; CEJ and properties 2–3 passed (3 passed) |
| `any-colour-cej` | treat a run with any `w:color` as an insertion (the CEJ cross-mutation) | Property 1 and the existing `test_red_font_is_not_a_revision_and_its_text_is_counted_once` **FAILED** on their revision assertions; properties 2–3 passed (2 passed) |
| `text-only-content-hash` | compute `content_sha256` from the first extracted text instead of the original bytes | Property 2 **FAILED** on the raw-byte digest assertion; properties 1 and 3 and CEJ passed (3 passed) |
| `filename-guessed-event` | mint a problem and an extra extracted unit when the display name contains "marked changes" | Property 3 **FAILED** on the ingestion problem assertion; properties 1–2 and CEJ passed (3 passed) |

The failure lines name the properties: a `RevisionEvent` appears where the
package declares none; the empty-string hash replaces a raw-byte digest; and a
name-guessed `ExtractionProblem` appears where the document reports no problem.
Baseline and fully restored runs were both **4 passed**. Both mutated product
files were restored to their recorded SHA-256 values, and `git status` showed no
product-source modification.

## 4. Local gates

| Gate | Command | Result |
|---|---|---|
| Target test file | `pytest tests/test_ooxml_revisions.py -q` | **42 passed** |
| Shard-cost witness | `pytest tests/test_ci_shard_coverage.py -q` | **16 passed** |
| Leakage pin | `pytest tests/test_no_reference_leakage.py::test_the_tree_carries_no_more_chinese_than_was_measured tests/test_no_reference_leakage.py::test_gitleaks_config_declares_no_path_allowlist -q` | **2 passed** |
| Lint | `ruff check .` | **All checks passed** |
| Format | `ruff format --check .` | **445 files already formatted** |
| Types | `mypy --strict src tests` | **Success: no issues found in 396 source files** |

These are local measurements on the worktree. The project's rule that a runner
measurement is the gate for a delivery still holds; this batch is the next
delivery after PR #148 and starts no CI run itself.

## 5. Boundaries

- No change under `src/`: the four mutations were temporary measurement steps,
  each restored byte-for-byte and re-hashed.
- No new test file, no shard-cost re-measurement, and no change to `CURRENT.md`
  or the version-graph acceptance record.
- No real material, material filename, manuscript words or person name in the
  tree; no write to a real pilot store.
- No push, no pull request, no whole-suite pytest run, and no change to a
  delivery branch.
