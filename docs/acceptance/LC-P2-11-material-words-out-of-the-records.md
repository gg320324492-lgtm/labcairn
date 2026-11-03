# LC-P2-11 — the material's words out of the records, and what watches them now

**Found by accident, and the accident is the finding.** While preparing the
fourth ring's record, the audit that counted Chinese text in tracked files turned
up **three documents that quoted the owner's unpublished material in its own
words** — in two of them, under a sentence that asserted the opposite. The
repository is public. The corpus is not.

**Measured, on the tree at `d693521`:**

| File | What it carried | Where it came from |
|---|---|---|
| `docs/acceptance/LC-P2-11-check-binding.md` | a distilled rule statement of **76** characters, its `context` of 37, the manuscript paragraph a tracked change was made in (quoted **twice**), four `rv-` case texts, both checks' questions and pass criteria, and two retrieval queries | commits `5f1e790`, `43ffff5` |
| `docs/acceptance/LC-P2-11-revision-distillation.md` | four cases labelled **"The mentor's own words"**, plus three rejected-case texts quoted to explain why they yielded no rule | `5f1e790` |
| `docs/handoff/CURRENT.md` | two of the advisor's comments quoted in full, and the group's writing template named by title with two of its own lines quoted | `0c32971`, `a724768` |

**And the sentence that made it a governance failure rather than a typo.** The same
paragraph of `CURRENT.md` in which the advisor's critique was quoted began
**"Nothing of the paper is in the repository."** The claim was printed in a file
that was, in that moment, false; nothing in the suite could see the difference,
because nothing was asked to. A promise that no witness can break is the failure
this project names in its own rules — and this is the first time it bit a
**confidentiality** promise rather than a behavioural one.

## 1. What replaced the quotations

Every quotation is now its **length and its SHA-256 prefix**, with the address the
store holds the words under:

> `| statement | **the words are not carried here** (removed 1 fragment: 76
> characters sha256 \`11dee2520513\`); the row is \`rule-1fcc9d1a2573d7b0\` v2 in the store |`

That is not decoration. A later reader can take the digest to the store, confirm
the row is the one the record means, and still be unable to read the sentence
without the corpus. The English that explains *what the mentor did* — deleted the
conjunction, deleted the unargued mechanism, replaced it with one that names its
chemistry — is unchanged, because the finding is the shape of the exchange.

No author name was ever in the tree: the three advisor names the store carries were
sought across all 689 tracked files and found in **none**.

## 2. The two witnesses, and why one is not enough

`tests/test_no_reference_leakage.py` is already the executable form of the
project's exclusion promises — *not committed* proven with `git ls-files`, the real
index. This joins that family, and both directions are watched.

**The pin.** `scripts/cjk_ceilings.py` measures the longest run of Han characters
in every tracked file — 48 files carry Chinese at all, and the longest runs are the
**project's own voice**: the bilingual README (29), the ADRs that state their rules
in the owner's language (20, 18, 15), the OOXML fixtures' synthetic sentences (15).
The test pins that measurement and fails on **added**, **grown** *or* **removed**,
so a carried-forward number reddens exactly like a new quotation does. The Chinese
is not the enemy; an unmeasured change to it is.

**The cap, because the pin could be widened.** The battery's M5 found the pin's
hole and closed it: a long Chinese run in a record, *with the table widened to
match and the file struck from the named list*, passed every assertion. So records
and the handoff are held to `RECORD_HAN_RUN_CAP = 14` — **a policy number, not a
measurement of the file it guards**. A quotation cannot be legalised by
re-measuring the page it was written into. `docs/acceptance/**` and
`docs/handoff/**` carry 14 today, and both instances are design vocabulary; raising
14 is a deliberate edit that a reviewer sees as a change of policy.

**The named records.** The three files above are additionally asserted to carry **no
Han run at all**, so a re-added quotation fails naming the file and what it means.

## 3. The mutations, with one that is expected to survive

Baseline green first (3 passed), every mutation isolated by a restore between them,
tree green again after. The first run of this battery got two of these wrong and the
corrections are in the table's cause column, not hidden.

| Mutation | Result |
|---|---|
| M1 a long Chinese sentence goes back into a record | **CAUGHT** — 3 red |
| M2 the measuring script quietly returns an empty map | **CAUGHT** — the pin's own sanity assertion |
| M3 a registered file's Chinese is removed, leaving a carried-forward number | **CAUGHT** |
| M4 a brand-new tracked file carries Chinese | **CAUGHT** — 2 red |
| M5 quote planted **and** table widened **and** file struck from the named list | **CAUGHT** by the cap — the pin alone passed it |
| M6 quote planted, table widened, name struck **and the cap raised to match** | **SURVIVED** — as designed, and stated |

**M6 is the honest boundary.** A person who moves the policy number defeats every
in-tree witness; what defends the promise then is the diff, the review, and the fact
that the number says out loud that it is policy. **The witness cannot tell the
corpus's Chinese from any other Chinese** — it watches length and change, not
provenance. A quotation short enough to hide in the vocabulary (the 2-character
two-character connectives this record once carried) is outside its reach; what
reaches those is the fingerprinting convention and the audit that found this.

## 4. What is not fixed

**The published history still holds the words.** The two `CURRENT.md` quotations
landed in `0c32971` (2026-10-31) and `a724768` (2026-11-01), both **already merged to
`origin/main`**; the acceptance-record quotations came in commits that were pushed to
`docs/debt-closures` on 2026-11-03. Redacting the tree does not unpublish a commit.
**Removing them from history means rewriting `main`, which is the owner's call and has
not been made or attempted here** — `main` is protected and never force-pushed. The
exposure is therefore: real, dated, public since those commits, and now closed going
forward and watched.

**Not a general leak test.** This watches Chinese runs. It does not scan for
manuscript text in images, filenames, or the digests themselves, it does not
cover a *romanised* quotation, and it is blind to a short one in a file it has
**already measured**: a two-character connective slips under a cap of 14. This
record's own first draft carried exactly such a quote, and what caught it was the
pin's `added` direction — the file was new, so nobody had measured it — not the
cap and not the named list. **A fresh record is watched; a grown one is watched
only past 14 characters,** and that is the number a reviewer is meant to see.

**The separate defect stays open.** The 24 comment rows whose `anchor_text_sha256`
is the SHA-256 of the empty string — 7 of them marked `resolved` — are a different
fault, owned by `anchor-empty-claim`, and are recorded in
[LC-P2-11-fourth-ring.md](LC-P2-11-fourth-ring.md) §4.

**Gates.** `ruff check .`, `ruff format --check .` and `mypy --strict src tests`
clean (389 source files); the three new witnesses pass; `README.zh-CN.md`, which a
mutation temporarily stripped, is **byte-identical to HEAD** again.
