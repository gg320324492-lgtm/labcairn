# LC-P2-14 — Batch 10: three negative witnesses — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) ·
**Routes watched:** [LC-P2-07](LC-P2-07-fidelity-baseline.md) (DOCX reader),
ADR-0004 A7 (unreadable is not empty), and
[LC-P2-08](LC-P2-08-acceptance.md) (the version graph).

**Status.** Three new witnesses are in the tree and mutation-checked. The
reconnaissance that named the three gaps is chain-external at
`E:\labcairn-local\batch10-recon\RECON.md` §1.3, §2 and §5. Its material was
read only; this record carries **no manuscript sentence, comment text, author
name, paper title, directory label, or real file name**. The fixtures are
synthetic bytes and neutral names built in existing test files. Counts and
structural classes below are the recon's, not quotations from the material.

**Measured:** 2026-11-05, Windows 11 (AMD64), Python 3.12, in a git worktree
whose `main` was `32cf6e15af40b14da8605cc241efa4057ff40470`. `PYTHONPATH`
pointed at this worktree's `src`. All pytest basetemps and all four temp
variables (`TEMP`, `TMP`, `TMPDIR`, `MPLCONFIGDIR`) were outside the repository
and distinct per run. No push, no pull request, no CI run, no product `src`
change, and no write to a real pilot store.

---

## 1. What batch 10 made necessary

| Structural class (chain-external count) | The guess a product must not make |
|---|---|
| 184 files in 8 numbered version directories; 17 `.doc` and 1 `.docx`; all 17 `.doc` start with the OLE2 signature and no first-party product OLE2 reader exists | An OLE2 container is not an OOXML package. "No addressable paragraphs" after a failed read is not an honest result. |
| 5 named marked pairs; 0 Word comments in the marked binary documents; 286 tracked revisions visible through an external object model; a coarse FIB/stream scan does not settle either count | Marker-like byte strings, their absence, or a name are not semantic evidence. Do not mint `CommentEvent` or `RevisionEvent` from them. |
| 28 path components under a discarded-figure class; 17 chart-project files; 14 repeated figure basenames whose corresponding files are not byte-identical; one numbered directory holds multiple textual branches | A filename, size, mtime or suffix does not choose one manuscript version or discard supporting files from the inventory. |

The two CEJ witnesses already in
[`LC-P2-14-cej-pilot.md`](LC-P2-14-cej-pilot.md) §2 hold two *different*
shapes: red font is not a revision, and a reviewer-named body paragraph is
not a comment. The second witness below is not a third copy of either: it
holds that byte strings resembling binary-format marker words, which a coarse
scan may or may not find, do not mint events.

## 2. The witnesses and their coverage

| # | Witness | Existing coverage | New contract |
|---|---|---|---|
| 1 | `tests/test_material_ingest.py::test_an_ole2_doc_is_inventoried_as_unparseable_not_an_empty_document` | `test_a_corrupt_archive_is_refused_and_says_so` refuses arbitrary non-ZIP bytes in the reader, and `test_a_material_with_no_adapter_is_recorded_with_a_disclosure` records an unclaimed `OTHER` kind. Neither feeds a `.doc` through ingestion and checks the resulting readability state. | Synthetic 512-byte OLE2 signature sector: `kind_for_path("...doc") is OTHER`, hash and size are the bytes', zero text units, exactly `no_adapter_for_kind`, `readability=unparseable`, a non-empty disclosure, and `extraction_version=no-adapter`. |
| 2 | `tests/test_ooxml_revisions.py::test_binary_marker_words_in_body_text_mint_no_events` | The two CEJ witnesses cover formatting and a named opinion; the corrupt-archive witness covers unreadable bytes. None covers a byte-string shortcut on a *readable* document. | A synthetic OOXML package has two paragraphs containing marker-like words and no comments part, comment ranges, or revision elements. `comments`, `revisions`, and `problems` are empty; both views keep the paragraphs once, in order. |
| 3 | `tests/test_material_walk.py::test_a_mixed_version_folder_inventories_candidates_without_picking_one` | `test_the_version_label_is_kept_verbatim_and_is_not_an_order` says a version label is not an order; `test_the_walk_finds_every_file_under_the_source_root` checks four plain files. Neither puts mixed candidates, discarded figures and chart sources through a real store walk and checks the version tables. | One synthetic version directory holds 4 text candidates, 1 discarded-figure file and 1 chart-source file. `ingest_workspace` records 6 distinct paths and 6 distinct hashes, skips exactly the two unclaimed formats, writes no failures, and leaves `paper_versions` and `version_edges` empty. |

No new test file was added, so the shard list, the cost table and the
evaluation manifest needed no new entry. The three files keep their existing
`unit` / `integration` / `unit` markers.

## 3. Mutation measurements

The harness at `E:\labcairn-local\batch10-negative\mutate.py` changed product
bytes in place, ran the named witness(es), restored from a sha256-verified
byte backup, and ran them again. It never used `git checkout`, never deleted
an assertion, and refused an anchor that was not unique. Five mutations were
measured; each produced an `AssertionError` in the intended witness, each
restored run was green, and each restored product file's sha256 equalled its
pre-mutation sha256.

| Mutation | Product file changed | Red / restored green | Byte restore |
|---|---|---|---|
| `.doc` mapped to `DOCX` | `ingest.py`, original `9712c6e3d7b3247e03790560e8bee5a8b0f74f24bc4a60c695a2b6f3379267cf` | witness 1 red (`OTHER` assertion), 1 green | equal |
| marker words mint a `CommentEvent` | `ooxml.py`, original `954e6825cbf7693d7cf72239f3bcd0c35cf7fdbc55eaddfcf0a2693de6fb105a` | witness 2 red, 1 green | equal |
| `w:delText` word mints a `RevisionEvent` | `ooxml.py`, same original | witness 2 red, 1 green | equal |
| existing reader refusal code renamed | `ooxml.py`, same original | **cross-mutation:** `test_a_corrupt_archive_is_refused_and_says_so` red, witness 1 green; restored 2 green | equal |
| name-based walk keeps 1 candidate, drops 3 | `walk.py`, original `fceec313322c34cec3e623bbc688a0059202bbdc91e21d8b11f5e949f1027cd9` | witness 3 red (`3 == 6` outcomes), 1 green | equal |

The fourth mutation is the cross-reference to property 1's existing reader
witness: it makes the already-present refusal claim fail, while the new
ingestion witness stays green because the two watch different layers. An
earlier marker mutation was discarded as **ineffective**: it appended a
guessed event before the collector reassigned its list, so the assertion
stayed green. It is not counted above. Machine-readable outputs, including
the failing assertion lines and both sha256 values for every run, are at
`E:\labcairn-local\batch10-negative\mutation-results.json`.

## 4. Local gates

| Gate | Command form | Result |
|---|---|---|
| three new witnesses | `pytest ... -k "ole2_doc or binary_marker_words or mixed_version_folder"` | 3 passed |
| whole affected files + shard witness | `pytest tests/test_material_ingest.py tests/test_ooxml_revisions.py tests/test_material_walk.py tests/test_ci_shard_coverage.py` | **121 passed**; includes the shard-cost witness |
| reference-exclusion witness | `pytest tests/test_no_reference_leakage.py` | **110 passed**; run without `PYTHONPATH` so the clean-wheel venv was not shadowed |
| ruff | `ruff check .` | passed |
| format | `ruff format --check .` | passed (445 files already formatted) |
| types | `mypy --strict src tests` | passed (396 source files) |

Two intermediate runs were *not* counted: one failed because a pytest
basetemp parent did not exist, and one clean-wheel import failed because
`PYTHONPATH` pointed at the worktree's source. Both were rerun with the
environment fixed; the clean-wheel witness itself was green, and no product
byte was changed by either. No full suite was run, per the work order.

## 5. Boundary

These witnesses hold the product's **honest refusal**: no OLE2 semantics are
claimed, no comment or revision is invented from bytes, and no version or
edge is chosen from names. They do **not** say that the external binary
documents contain zero comments or zero revisions. That positive question is
outside the first-party product's current reader and outside this record.
No real material bytes, file names or text are in the repository; the
acceptance evidence outside the repository contains counts, hashes and
structural classes only.
