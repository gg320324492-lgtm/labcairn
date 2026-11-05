# LC-P2-14 — The batch-9 replies pilot: agriculture and MNB response letters — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) (the blind evaluation
and ablation) · **Route under test:** [`LC-P2-09`](LC-P2-09-acceptance.md) (the feedback
chain) · **This record:** a **read-only routing** result on one material batch.

**Status.** The pilot ran end to end against the real material and its evidence lives
outside the repository. **No full ingestion was performed, no product code was changed,
and no test was added or altered.** The English revised manuscripts the letters describe
are not in the material, so this record makes no settlement and compares no revision.
**Nothing here rates the material, the reviewers or the answers.**

**What this record does not carry.** The papers' titles, their sentences, the reviewers'
comments, the authors' answers, the file names and the names of the people involved are
not in this file and not anywhere in the repository. The material is referred to as
**batch 9**, each paper by a group label (agriculture, MNB, water supply) and each letter
by a neutral id (`agri-r1` … `mnb-r2`) and the first twelve hex characters of its
sha256. The pilot's own outputs — indices, counts and hashes only — live outside the
repository under `E:\labcairn-local\batch9-pilot\`, beside the read-only material.

**Measured:** 2026-11-05 on the worktree branch over `main` at
`4a9b70a`, on Windows 11 (AMD64), Python 3.12.13. The reconnaissance that names the
material and its shapes is chain-external (`E:\labcairn-local\batch9-recon\RECON.md`);
the material directory itself is not named here.

---

## 1. What was routed

Six English response letters entered a pilot workspace under neutral names, were ingested
by the product's own ingestion, and were registered as one version each of two pilot
projects. `record_replies` then recorded one exchange per `Point` / `Response` pair, and
`list_replies` read the rows back. The pairing rule is the letter's own layout:

1. a `Point …` marker opens the objection;
2. the first `Response …` marker after it opens the answer;
3. the pair ends at the next `Point …`.

The rule is stated here so it can be contested; it is the pilot's judgement, and the
product supplies the words. Both parties are `reviewer` / `author`, and the pairing grade
is `observed` — the only grade the layout supports.

| Paper | Letters in material | Letters recorded | Pairs |
|---|---|---|---|
| Agriculture | 4 | 4 | 20 |
| MNB | 3 | 2 | 24 |
| Water supply | 1 | 0 | 0 |
| **Total** | **8** | **6** | **44** |

The MNB third letter is the R1+R2 text re-issued; it was parsed (24 pairs) but recorded
nowhere. The water-supply letter is mixed-source and was not touched.

## 2. Per-letter counts

Counts are the product reader's (`labcairn.material.ooxml.read_document`); paragraph
numbers are document order over every `w:p`, tables included.

| Letter | sha256 prefix | Paragraphs | `Point` markers | `Response` markers | Pairs | Rows | Read back | Words match |
|---|---|---|---|---|---|---|---|---|
| agri-r1 | `33ed0b6c160c` | 63 | 2 | 2 | 2 | 2 | 2 | 2 |
| agri-r2 | `dbf210b4f7a2` | 35 | 6 | 6 | 6 | 6 | 6 | 6 |
| agri-r3 | `9e7afbf81c6d` | 23 | 5 | 5 | 5 | 5 | 5 | 5 |
| agri-r4 | `a9d5cb6ab966` | 73 | 7 | 7 | 7 | 7 | 7 | 7 |
| mnb-r1 | `367acbe78c0e` | 66 | 5 | 5 | 5 | 5 | 5 | 5 |
| mnb-r2 | `efabbc99e036` | 131 | 19 | 19 | 19 | 19 | 19 | 19 |
| **Total** | | | **44** | **44** | **44** | **44** | **44** | **44** |

The merged MNB letter (`99ccab62606e`, 169 paragraphs) parses to 24 points and 24
responses. It is a re-issue, not a third round; §4 is about it.

## 3. What the row cannot hold whole

Each pair was recorded as **one** exchange: the objection paragraph is the `Point`
marker's paragraph, the answer paragraph is the first `Response` marker's paragraph. No
pair was split into sub-exchanges and no answer block was duplicated. The parts of a pair
the product's two-index row cannot carry are counted, not invented.

| Shape | Pairs | Where |
|---|---|---|
| Objection spans more than one paragraph (sub-items) | 2 | mnb-r2 paragraphs 78, 118 |
| Answer spans more than one paragraph | 35 | all six letters |
| Answer complete in one paragraph | 9 | agri-r3 (3), agri-r4 (2), mnb-r2 (4) |
| `Point` with no `Response` | 0 | — |
| `Response` with no preceding `Point` (orphan) | 0 | — |

- The two multi-paragraph objections are MNB R2 points with A–E / A–C sub-items. The row
  holds the marker paragraph; splitting them into 5 + 3 exchanges would invent a pairing
  the letter does not state.
- For the 35 multi-paragraph answers, the row holds the answer's opening paragraph. The
  continuation paragraphs and answer tables stay outside the store. This is the product's
  documented limit, not a parsing loss.
- "Only red text and no answer" did not occur as a structural case: every `Point` marker
  reaches a `Response` marker, and red font is never on the objection side. Red font was
  not used as a pairing signal.

## 4. Read-back and the merged letter

The scratch store was opened after the run with SQLite `mode=ro`, directly rather than
through the application layer. **44 rows**, 44 distinct ids, two projects (20 + 24), six
`paper_versions` and the six recorded letters only. Every row's two hashes were recomputed
from the paragraph at the index the row names: **44 / 44 match**, 0 mismatches,
`PRAGMA integrity_check` `ok`. The store's main-file SHA-256 is
`088e6393f563c1d0e96e7eb2f1edb2237de38add4f1f6e7a1ae6f605e2bdf109`
(1,138,688 bytes); row counts come from SQL over the live store, not from the file hash.

The merged MNB letter was parsed by the same rule. Its 24 pairs (5 + 19) have the same
structure as R1+R2; 9 of 24 are byte-identical in both halves to a recorded pair, and the
rest are the same text re-issued with layout and wording differences. The reconnaissance
measured 7-gram containment 0.990 against R1 and 0.983 against R2. **It was recorded
nowhere**, so the store holds 44 rows, not 68.

## 5. What this proves, and what it does not

**It proves** the reply table and `record_replies` / `list_replies` hold this material's
exchange shape with no change to the product: one paragraph of objection, one of answer,
a party on each side, across two papers and six letters. **It does not prove** the chain
can route the answer *range* or the sub-item shape as one record; §3 states the two
limits and their counts at this material.

**The English revised manuscripts are not in this material.** The letters answer English
submissions, while the four readable manuscripts are Chinese, and the recon found no red
quotation reaching the manuscript text. A settlement over these replies would have
nothing to point at, so none was attempted. The same fact rules out a version graph for
the agriculture and MNB papers.

**No full ingestion, no score.** The 44 exchanges are a property of the letters, not a
measure of their quality.

## 6. Where the evidence lives

| What | Where |
|---|---|
| Recon (chain-external) | `E:\labcairn-local\batch9-recon\RECON.md` |
| Pilot script and result (indices, counts, hashes) | `E:\labcairn-local\batch9-pilot\run_pilot.py`, `route.json` |
| Independent read-back | `E:\labcairn-local\batch9-pilot\verify.py`, `verify.json` |
| Human-readable result | `E:\labcairn-local\batch9-pilot\RESULTS.md` |
| Scratch store (this pilot's own) | `E:\labcairn-local\batch9-pilot\pilot.db` |
