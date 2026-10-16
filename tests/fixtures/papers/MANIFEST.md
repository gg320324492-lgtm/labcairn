# Real-paper fixtures — provenance and licence

**Retrieved:** 2026-10-17
**Licence:** all three are **CC BY 4.0**. Verified per paper from the arXiv
abstract page, which carries the licence link
(`creativecommons.org/licenses/by/4.0/`). Not assumed from the venue.

CC BY requires attribution, so this file **is** the attribution: title,
authors, source and licence for each paper, as CC BY 4.0 §3(a) asks.

Papers carrying `NC`, `ND` or `SA` variants were rejected on purpose.
Those add obligations a test fixture should not impose on the repository.

---

## Why real papers are here at all

`docs/adr/ADR-0008-pdf-ingestion-library.md` records five measured
constraints on PDF ingestion and states that its candidate replacement for
gutter detection — *line support* — is **unproven**, because it was
reasoned from hand-built fixtures. Synthetic PDFs are built by the same
person who then tests them, and this project has already been bitten by
that: a hand-built fixture was used to claim a property of pdfplumber
that turned out to be a property of the fixture.

## What these three are for

All three are **single-column**, which makes them **negative** fixtures.
Their job is to fail loudly when a segmenter splits a column that is not
there. That is one of the two directions; the other is untested here and
is recorded as an open item below.

| File | Why it is here |
|---|---|
| `arx-2610.10596.pdf` | Smallest, 9 pages, plain single-column text. The baseline a segmenter must leave alone. |
| `arx-2610.12393.pdf` | 32 pages, math-heavy: display equations and many short lines. **This paper defeated a plausible segmenter** — its median row width is under 75% of page width, so a "narrow rows mean two columns" heuristic classifies it as two-column when it is plainly one column. Kept as an adversarial negative. |
| `arx-2610.09396.pdf` | 29 pages, contains a full-width **table** whose cells produce two line-start clusters. A table that looks like a column split is the most likely false positive in real material. |

---

## Provenance

| Field | `arx-2610.10596.pdf` | `arx-2610.12393.pdf` | `arx-2610.09396.pdf` |
|---|---|---|---|
| Title | Dijkstra Is NOT Greedy: A Global-to-Local Proof of Correctness | HRIL: Learning Multimodal Synergy via Higher-Order Tensor Modeling | ARCS: Towards Precise Text-to-SQL via Structured Disambiguation |
| Authors | Wang, Shengbao | Dai, Qun; Wen, Liangjian Duan, Jiang; Dai, Yong | Hu, Yihao; Feng, Yanlin Otani, Naoki; Bhutani, Nikita |
| Source | https://arxiv.org/abs/2610.10596 | https://arxiv.org/abs/2610.12393 | https://arxiv.org/abs/2610.09396 |
| PDF | https://arxiv.org/pdf/2610.10596 | https://arxiv.org/pdf/2610.12393 | https://arxiv.org/pdf/2610.09396 |
| Licence | CC BY 4.0 | CC BY 4.0 | CC BY 4.0 |
| Pages | 9 | 32 | 29 |
| Bytes | 267,479 | 720,429 | 1,685,086 |
| SHA-256 | `6da9f8057e8cc7bafcf76316d660276f40c2e4a87230fa418e28cde51143d700` | `2429674e16c9b9dc2bb584d71e307285853fca11e356847d7e84508538799b9d` | `292eae176b6ea072cb23b163f861954bab2fd7e1f973d8f8fcd2575aa1338520` |

The SHA-256 values are re-checked by `tests/test_paper_fixtures.py`, so a
fixture cannot be silently replaced — which is the failure mode this
project cares most about, since a swapped fixture would make a test pass
against material nobody chose.

---

## What was measured on them

Measured, not assumed:

- **All three are single-column.** Dominant line-start x is 108, 72 and
  108 points respectively, holding 52–64% of body lines. A two-column page
  shows two line-start peaks at least 80 points apart.
- **Space glyphs are almost absent.** In the first ten pages, space
  characters are 6 of 18,559 (0.03%), 15 of 31,846 (0.05%) and 348 of
  32,198 (1.08%). Ordinary running text is roughly 15–18% spaces. This is
  ADR-0008 constraint 3 confirmed on real material rather than on a
  synthetic fixture: joining character records does not reproduce the
  source string, because these PDFs space words by positioning.
- **Intra-line gap sizes have no valley.** On `2610.12393` the gap
  histogram runs 4pt:127, 5pt:35, 6pt:20 … 43pt:8 — essentially flat.
  Word gaps and a column gutter would sit on one continuum, so **no
  threshold on gap magnitude can separate them.** This is why every
  magnitude-based segmentation rule tried underperformed, and it is the
  strongest argument yet for a positional signal rather than a size one.

## Open item — these cannot test column detection

**There is no two-column material here, and the reason is not an oversight.**
Eleven CC BY arXiv papers were downloaded and classified by line-start
peaks. **All eleven are single-column.** Recent arXiv uses single-column
submission format; the only pages showing two line-start clusters were
**tables**, verified by reading the text.

So the false-positive direction is covered — a segmenter must not split
these — and the **false-negative direction is untested**: nothing here
establishes that a segmenter will find two columns in a two-column paper.
Until such material is obtained, ADR-0008's line-support hypothesis stays
**unproven**, and any test asserting two-column detection must be written
against synthetic fixtures with that limitation stated in its name.

Sourcing two-column CC-licensed material is an open task. Older arXiv
papers are predominantly two-column, but CC BY adoption there is rarer, so
the intersection is narrow.
