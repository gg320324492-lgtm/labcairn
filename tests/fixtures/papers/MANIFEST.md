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

## Provenance and attribution

Listed per paper rather than in a wide table. An earlier revision used a
table, and two of the cells were corrupted by delimiter collision —
`"Wen, Liangjian Duan, Jiang"` and `"Feng, Yanlin Otani, Naoki"` — which
also truncated one paper to five of its ten authors. CC BY 4.0 §3(a)(1)(A)
asks for identification of the creator(s), so a list that silently drops
five of ten is not a formatting nit; it is an unmet condition on a
repository that has no `LICENSE` file to carry it instead.

### `arx-2610.10596.pdf`

- **Title:** Dijkstra Is NOT Greedy: A Global-to-Local Proof of Correctness
- **Authors (all):** Wang, Shengbao
- **Source:** <https://arxiv.org/abs/2610.10596> · **PDF:** <https://arxiv.org/pdf/2610.10596>
- **Licence:** CC BY 4.0 — <http://creativecommons.org/licenses/by/4.0/>
- **Pages:** 9 · **Bytes:** 267,479
- **SHA-256:** `6da9f8057e8cc7bafcf76316d660276f40c2e4a87230fa418e28cde51143d700`

### `arx-2610.12393.pdf`

- **Title:** HRIL: Learning Multimodal Synergy via Higher-Order Tensor Modeling
- **Authors (all ten, in order):** Dai, Qun · Wen, Liangjian · Duan, Jiang ·
  Dai, Yong · Wang, Dongkai · Wang, Maolin · Wang, Mingjie · Liu, Jianzhuang ·
  Yan, He · Kang, Zhao
- **Source:** <https://arxiv.org/abs/2610.12393> · **PDF:** <https://arxiv.org/pdf/2610.12393>
- **Licence:** CC BY 4.0 — <http://creativecommons.org/licenses/by/4.0/>
- **Pages:** 32 · **Bytes:** 720,429
- **SHA-256:** `2429674e16c9b9dc2bb584d71e307285853fca11e356847d7e84508538799b9d`

### `arx-2610.09396.pdf`

- **Title:** ARCS: Towards Precise Text-to-SQL via Structured Disambiguation
- **Authors (all):** Hu, Yihao · Feng, Yanlin · Otani, Naoki · Bhutani, Nikita
- **Source:** <https://arxiv.org/abs/2610.09396> · **PDF:** <https://arxiv.org/pdf/2610.09396>
- **Licence:** CC BY 4.0 — <http://creativecommons.org/licenses/by/4.0/>
- **Pages:** 29 · **Bytes:** 1,685,086
- **SHA-256:** `292eae176b6ea072cb23b163f861954bab2fd7e1f973d8f8fcd2575aa1338520`

The files are **verbatim copies**; nothing has been modified, so CC BY's
modification-indication requirement is not engaged. None of the three PDFs
carries a copyright notice on its pages, so §3(a)(1)(C) and (E) are not
engaged either.

One name was worth checking rather than trusting: arXiv's metadata gives
`Yan, He` for this paper's ninth creator, which reads like an inversion.
The byline on page 1 reads `HEYAN`, i.e. given name first and surname last,
which is the same person and the same `surname, given` order as every other
entry here. It was checked against the document rather than assumed.

The SHA-256 values are re-checked by `tests/test_paper_fixtures.py`, so a
fixture cannot be silently replaced — which is the failure mode this
project cares most about, since a swapped fixture would make a test pass
against material nobody chose.

---

## What was measured on them

Measured, not assumed:

- **All three are single-column.** Dominant line-start x is **72, 108 and
  108** points for `10596`, `12393` and `09396` respectively, holding
  **60.1%, 64.3% and 51.5%** of body lines. A two-column page shows two
  line-start clusters at least 80 points apart.
- **Space glyphs are almost absent.** In the first ten pages, space
  characters are 6 of 18,559 (0.03%), 15 of 31,846 (0.05%) and 348 of
  32,198 (1.08%). Ordinary running text is roughly 15–18% spaces. This is
  ADR-0008 constraint 3 confirmed on real material rather than on a
  synthetic fixture: joining character records does not reproduce the
  source string, because these PDFs space words by positioning.
- **Gap magnitude cannot separate a word gap from a gutter.** Measured on
  `arx-2610.12393`, first ten pages, characters grouped by
  `round(doctop, 1)`, sorted by `x0`, keeping gaps greater than 0.5pt:
  **n = 5016**, p50 = 2.51pt, p75 = 3.50, p90 = 16.68, p95 = 37.44,
  p99 = 135.92, max = 334.3.

  An earlier revision of this file described the distribution as
  "essentially flat". **That was wrong**, and the correction matters more
  than the conclusion it was attached to. The distribution is not flat: it
  falls from 26 buckets at 6pt to around 10 at 45pt. What it does instead
  is **decay continuously with no break**, which is the property that
  matters. Buckets 6–44pt run 26, 26, 21, 32, 36, 51, 26, 30, 17, 36, 16,
  27, 19, 19, 8, 8, 13, 12, 7, 9 … 8, 11, 7 — every integer value in the
  range is populated, and **4% of all gaps fall in 15–30pt**, which is
  where a real gutter lives. They grade into the word gaps below them with
  nothing to cut on.

  So a threshold set anywhere in gutter territory slices straight through
  the word-gap population. This is the strongest available argument for a
  positional signal rather than a size one — and it took a real paper to
  see, because the hand-built fixtures had a valley by construction.

  The counts are reproducible with the method above. An earlier revision
  quoted `4pt:127, 5pt:35, 6pt:20 … 43pt:8` under an unrecorded method,
  and a reviewer could not reproduce them under six variants of line
  filtering and page scope. **A measurement whose method is not written
  down is not evidence**, which is why the method is now part of the claim.

## Open item — these cannot test column detection

**There is no two-column material here, and the reason is not an oversight.**
Eleven CC BY arXiv papers were downloaded and classified as single-column;
three were kept. The remaining eight were discarded and **are retained nowhere**,
so that count is *not independently checkable* — it rests on this repository's
author's record alone, and should be read that way.

The classification also needs a caveat that a review surfaced. It was done by
recurring **line-start x**, and that method has a failure mode: grouping
characters by baseline across the full page merges the two columns of a
two-column page, because the columns share baselines, so it reports one column
for material that plainly has two. On the three kept fixtures the conclusion
was re-established by two independent methods — recurring line-start x *after*
splitting each baseline into column-local runs, and right-edge occupancy
against a two-column control. On the eight discarded papers it was not, and
they were single-column by inspection of the same kind that caught the earlier
error.

So the corpus verifies one direction — a segmenter must not split these — and
leaves the other untested: **nothing here establishes that a segmenter will
find two columns in a two-column paper.** Until such material is obtained,
ADR-0008's line-support hypothesis stays **unproven**, and any test asserting
two-column detection must be written against synthetic fixtures with that
limitation stated in its name.

Sourcing two-column CC-licensed material is an open task. Older arXiv papers
are predominantly two-column, but CC BY adoption there is rarer, so the
intersection is narrow.
