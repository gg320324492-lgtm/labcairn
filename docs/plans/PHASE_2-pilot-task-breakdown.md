# The Phase 2 pilot — task breakdown

**Status:** the first real model request is done (2026-10-31), the corpus
is chosen and in place, and the material is organised in a library of its
own. The readers are **three independent sessions** — two blind readers
and a third, the arbiter — which is the arrangement the annotation guide
already used for the gold set, and §1.1 says plainly what that number
does and does not measure.

**What the pilot is.** The first time LabCairn reads **the owner's real
paper** rather than a fixture: the versions, the comments, the advisor's
words, and a model's judgement about them — with a person's consent at
every step that touches anything outside the machine.

**What it is not.** It is not a benchmark, and it is not a claim that the
guidance memory works on real manuscripts. The corpus is one paper, and
the number the pilot produces is an agreement between two independent
readings of it.

---

## 1. Where the pilot stands

| # | The thing | State |
|---|---|---|
| 1 | The corpus | **chosen.** The owner's paper: nine Chinese process drafts, an English version, and a tracked-changes copy. One of them (`manuscript-1.docx`, the English version of version 9) is ingested into the pilot workspace; the rest are one `sources ingest` away. |
| 2 | The first real model request | **done**, twice. A material-free one, which proved the path and disclosed nothing, and a business one that carried 507 characters of the draft under an approval that binds them. See §2. |
| 3 | The two readers | **three independent sessions**, working in parallel in their own directories, blind to each other's work. The third is the arbiter. |
| 4 | The corpus's owner | **the owner.** The paper is theirs; it never enters this repository. |
| 5 | The material library | **built**, outside the repository: `E:\labcairn-local\materials-library`, with the versions under descriptive names, the advisor's comments and the tracked revisions extracted per version, the annotation guide beside them, and the untouched archive with a manifest of every file's original name and hash. |

## 2. What the first real request measured

The request was deliberately **material-free**: it asked the model to judge
a manuscript without being given one, and the model answered honestly —
*"No manuscript or revision materials were provided for evaluation."* That
is the right answer, and it is the answer that proves the path works
without disclosing a word of the paper.

What it proved, on a real endpoint, with the product's own gates:

- the **capability probe** measured four of four capabilities on the
  owner's endpoint (tool calls, native structured output, prompted
  structured output, usage reporting);
- the **budget's preflight** accepted a token ceiling of 4000, because the
  ledger carried the probe's result and the endpoint's usage is measured;
- the **material gate** refused twice before it permitted anything — once
  because the grant's scope did not reach the material, once because the
  approval's task scope did not match — and each refusal named its remedy;
- the **exchange record** landed with digests and counts and the
  credential by its fingerprint: no plaintext key, no prompt, no answer;
- the **answer was decoded against the schema it was asked for**, and the
  approval was consumed exactly once. Three earlier approvals were granted
  and never spent, because every refusal happened before the spend.

**The one thing the pilot did not exercise:** a model's answer entering the
evidence ledger as a `model_proposal`. That entry needs a **locator in the
material**, and this request carried no material — so there was nothing to
bind. Recording a proposal about a manuscript the model never saw would be
exactly the thing this project refuses to do. The proposal lands in the
pilot's next request, the one that carries an excerpt.

**And it did.** The business request carried the advisor's comment, the
passage it is anchored to and the paragraph it sits in — 507 characters,
named in the approval's arguments and so bound by its digest — and **the
answer entered the ledger as a `model_proposal` on `planned`, bound to the
address of that comment.** The address resolves inside the owner's own
draft, and the record carries the model's own words as its quotation.
What the model said and how it compares with the readings lives in the
library; the repository is public, and the pilot's own decisions keep the
paper's business out of it.

## 3. The gaps the pilot found, and what they cost

| The gap | What it means for the pilot | The remedy |
|---|---|---|
| **No product door writes an access grant.** `access_grants` has a model and a reader, and nothing that writes it — the tests insert the row by hand. | The pilot's material-purpose grant — the very thing the transmit gate judges the request against — has to be written by a script outside the product. | A product operation that issues a grant, with the grant's scope, purpose, destination and expiry as its arguments, and a witness that a grant names one destination and one purpose. |
| **The probe's result is measured but not persisted.** `doctor --probe` measures and prints; the run that needs the capabilities has to probe again. | Every run that needs a schema pays for three more requests, and two runs can disagree about the endpoint's abilities. | Persist the probe record — ADR-0002's SQLite table, LC-P1-05's territory — keyed on the endpoint fingerprint the probe already computes. |
| **The model path has no CLI.** `request_model` is an application-layer operation; the operator reaches it through code. | The pilot's operators run a script, not a command, and the approval they grant is granted for a command that does not exist. | A `labcairn task model-request` command that asks for the approval the way `task figure` does — printing the request it will make. |
| **`request_model` is not exported from `labcairn.application`.** The demo and the test import the module path directly. | A caller must know a module path to call the operation the application layer offers. | Export it, with the capability table row the other operations have. |
| **Six domain modules reach past the application layer to the store.** `labcairn.guidance.{rules,retrieval,distil}` and `labcairn.roles.{spec,guidance,critique,trajectory}` import the store's rows directly, and the repository's own witness says so. | **The pilot's next operation would be a surface reading the store without the layer**, which is the hole the witness exists to close. | Application-layer operations that own those reads, and the six modules calling them. This is LC-P2-11's and LC-P2-12's scope, and it is **the next piece of work**, not a repair to bolt on here. |
| **Nothing advances a record's status.** The machinery is there — `evidence/store.py`'s `advance()` runs the named checks, appends the verdicts and moves the record, and the suite drives it twenty-seven times — but **no operation in `src/` calls it**: not the application layer, not the API, not the CLI. | **A proposal cannot be confirmed or disputed.** The model's answer sits at `planned` for ever, because the one step that would take it to `verified_by_rule` or `user_attested` has no door. This is the pilot's step 4, and it stops there. | An application-layer operation that advances a record — the checks named, the policy digest bound, the refusal named — and a CLI command that asks for it. The machinery is tested; what is missing is the door. |

## 4. The pilot's shape

1. **Ingest the versions.** The nine drafts and the English version, each
   a `PaperVersion` in the version graph, each edge saying what changed.
   The tracked-changes copy is the version graph's sharpest test: its
   revisions are the advisor's own words, already marked.
2. **Two blind readings.** The same comment, read by two sessions that
   have not seen each other's labels. Each reading is a `label` row.
   **The agreement between them is the pilot's number** — and it is
   reported, not targeted: LC-P2-10 says the work order reports
   inter-annotator agreement rather than requiring it.
3. **The arbiter reads only the disagreements.** A third session, given the
   two labels and the comment, says which is right. **The arbiter is a
   third reader, not one of the two** — the same reader twice is one
   reading.
4. **The model's judgement enters as a proposal.** One real request with
   an excerpt and a locator: the model's card enters the ledger as a
   `model_proposal` on `planned`, bound to the address it speaks for, and
   a person confirms or disputes it. **A model's say-so never becomes a
   rule by being retrieved often** — that is LC-P2-11's line, and the
   pilot is where it is tested on real text. **The proposal is in the
   ledger; the second half of this step is not yet possible**, because
   nothing advances a record's status (§3's last row) — and that is the
   pilot's next piece of work, not a step it can skip.
5. **The measurement.** What the pilot produces: the agreement number, the
   count of proposals a person confirmed, and the cases where the model's
   card and the advisor's comment disagreed. **The cases where the model
   was wrong are the pilot's most valuable output**, and they are recorded
   as such.

### 4.1 What the agreement number is, and what it is not

**The number measures how far two independent readings of the same material
converge. It does not measure how far two people would agree.** The readers
are sessions of one model, not two people, and the annotation guide §1.0
says so of the gold set, whose labels were read the same way.

This is stated here rather than only in the guide because the pilot's
number will be read against the gold set's, and the two are the same kind
of number only if both are described the same way. **A human reading of the
same corpus is the comparison the number is meant to be read against.**

## 5. The decisions waiting for the owner

1. **The corpus's breadth.** One paper (nine versions) or three to five.
   The reuse matrix records the corpus as three papers and the
   locator-validity metric as not measured, so LC-P2-11's retrieval has
   nothing to be measured against until the corpus is widened.
2. **Whether the real request carries the paper's text.** The first one
   did not. The pilot's business request must, and that is the owner's
   decision to make per request — the grant's scope says which text may
   go, and the approval's digest says which excerpt.
3. **Whether the pilot's next operation is the store-boundary repair.**
   The six domain modules that reach past the application layer are the
   pilot's next piece of work, and the pilot's own operation would be the
   first surface to read the store through them.
