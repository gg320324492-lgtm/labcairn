# The records' citations, watched

**Status:** CLOSED — the witness, its arms and its exception list are in the tree.
**Date:** 2026-11-28.
**Branch:** `claude/angry-gould-0c9892` (worktree `angry-gould-0c9892`), based on
`main` at `c8117b9`. Nothing pushed; no pull request; no CI run.
**Witness:** `tests/test_record_citations.py`, landed as `94bf9b6` and registered
in `tests/evaluation/manifest.py` and `.github/ci-shards.json` by the same
commit. Its measured cost there is 1.7 s on Ubuntu and 2.12 s on Windows.

This record says what that witness watches, what it deliberately does not
watch, what its first run measured, and the mutation check that shows each of
its mechanisms decides rather than passes.

## 1. The gap it closes

`tests/test_status_consistency.py::test_a_commits_cited_on_the_board_exist_here`
watches the commits the **status board** cites, and its docstring says why the
scope is the board: `UPSTREAM_REFERENCES.md` and the ADRs cite other projects'
histories on purpose, and an allowlist that grows with each upstream study is
not a check.

The acceptance records, the handoff and the plans were not covered. The
delivery-line rewrite re-pointed **seventy-two citations in eighteen files**
with a script of its own, and the script found no stale citation afterwards —
but **no test in the tree would have gone red if it had re-pointed one of them
at the wrong commit.** A citation that looks right and names nothing is the rot
this witness exists for.

## 2. What it watches

Every `*.md` under `docs/acceptance`, `docs/handoff` and `docs/plans` — the
documents that record *this* project's own work. `docs/UPSTREAM_REFERENCES.md`
is read too, but only as a **catalogue**: the foreign projects whose revisions
this tree records, and the pins it holds for them. The catalogue is data; the
witness keeps no list of foreign hashes.

The shapes it considers, and why the width decides:

| shape | judged? | why |
| --- | --- | --- |
| A code span of **7–39** hex that this checkout resolves | yes | an abbreviation of an object this repository has |
| A code span of **7–39** hex that this checkout cannot resolve | no | the same shape is a CI run id, a digest's prefix, an upstream abbreviation, or a word (`succeeded` contains `cceeded`) |
| A code span or bare token of exactly **40** hex | always | a SHA-1 object id, and the width the records use when a citation must survive a rewrite |
| A **bare** full id — a table cell, a command line, a `measured_at` value | always | the records write citations this way too |
| A URL under `github.com/gg320324492-lgtm/labcairn/{commit,tree,blob}/` | always | the URL itself says the claim is about this repository |
| **41 or more** hex | no | a git object id is a SHA-1 digest, at most 40 characters; a 64-character token is a SHA-256 content digest |

How it tells the kinds apart:

- **Resolution comes first.** A token this repository's object database
  resolves to a commit *is* a commit of this repository, whatever the prose
  says. A foreign project's revision and a fixture's content hash cannot
  resolve here.
- **The introducer decides the object kind.** Only an object phrase names a
  git tree or blob: `the tree that <commit> carries`, `^{tree}`, `tree
  equality`, `the blob`. Plain `the tree` is this tree's word for the
  workspace state, and its value is a commit; `**Tree:**` is a commit field.
  A noun inside the object phrase (`branch commit` in `the tree that branch
  commit carries`) does not override it; a noun that starts after the phrase
  does.
- **Reachability is HEAD, the remote branches and the tags** — the refs a
  clone of the published repository carries. Local branches other than the one
  checked out are **not** counted: an unpushed branch is not a place a clone
  can look, and a branch cut before a rewrite can still hold an object the
  rewritten line dropped. Pull request refs, backup refs, the stash and the
  reflog are excluded for the same reason.
- **Only an unresolvable full id needs provenance.** If its unit — the
  markdown block and the headings above it — names a foreign source, the token
  belongs to that source. A foreign source is a URL to another repository, a
  path into the upstream clones (`labcairn-upstreams`, `_references`,
  `.upstreams`), or a project the catalogue pins a revision for. If the
  catalogue cannot be parsed, the foreign citations turn red rather than
  passing silently.

## 3. What it does not watch

- `docs/adr` and `docs/UPSTREAM_REFERENCES.md` themselves, whose subject is
  foreign history on purpose; `docs/REVIEW-DOSSIER.md`, which has its own
  witness in `tests/test_review_dossier.py`.
- **Fenced code blocks**: transcripts of command output, not claims; a `#`
  line inside one is a shell comment, not a heading.
- **Block quotes**: a quoted hash is an owner's words, a command's output or a
  finding a review reported, not a claim this repository makes. The exclusion
  has its own two-direction arm below, so it cannot become a tolerance.
- **Prose**: a sentence is not a witness. This file checks ids, paths, kinds
  and reachability.
- **A short token this checkout cannot resolve**, as above.
- **A re-point to a reachable commit.** No existence witness can tell a right
  commit from a wrong one when both are ancestors of a branch. What is caught
  is the failure that leaves a citation naming something the tree does not
  have: a mistyped digit, an old id outside every branch, a tree or a blob in
  a commit's place.
- **A shallow checkout.** The reachability arm skips, with its reason, when
  `git rev-parse --is-shallow-repository` says the history is not there; the CI
  shard job fetches `fetch-depth: 0`, so the arm runs there.

## 4. The exception list, and why each entry is there

A hash that names something this repository **deliberately no longer has** may
be declared in `ABSENCES` in the witness, and every entry must say why. An
entry with no reason fails, an entry that names something a branch still
reaches fails (dead weight), and a missing full id that is neither a foreign
revision nor a declared absence fails. The list is not a tolerance.

| id (prefix) | what it is | why the repository no longer has it |
| --- | --- | --- |
| `25bad72383706e941e9ec22846f802033f6dea02` | G4's branch commit, the state its acceptance record measured | the work landed by squash as `d65254d`, whose tree is this commit's; the branch was deleted |
| `d74ac7aa98069d647c4bbdfd3299280d12d24954` | PR #195's branch commit, the head the shard costs were measured on | landed by squash as `b2e3661`; the branch was deleted, and the record says the id is in no history `main` has |
| `e16d82d3ce49d6859ff4c34b18e1880dc7ae417d` | a merge commit on PR #195's branch, measured by the re-anchor run | the branch was squash-merged and deleted |
| `0582cc533a8a52fe8df0e5399c703bf053427925` | the head of PR #194's run, which failed the same way an hour later | a merge of `main` into that branch; the branch is gone |
| `ec260b551655eac6dfc023eb93befa853084d608` | the tree `d74ac7aa98069d647c4bbdfd3299280d12d24954` carries, named beside it | unreachable with its commit; no surviving commit carries that tree |
| `ecdfb94ce018e5c1fa2c7fc9b4348bd188b25cad` | the blob that carried a person's name in the delivery line | the line was rewritten to replace that document; no branch or tag of the published repository reaches it |
| `a399bfb1331786bba5db4ecb9f49f064ee4a0a8e` | the leaked commit before the delivery line was rewritten | the record names it only to say what became `9c7eb19…`; the rewrite moved it out of the branch's history |
| `40609d659fc434556fbd8f88ddd8bc4c3e04f3d4` | the delivery line's tip before the rewrite | re-hashed when the leaked commit was replaced; no branch carries it |

Eight entries: six commits, one tree, one blob. Four foreign revisions are
named in the records and are **not** exceptions — they belong to other
repositories and are skipped by the provenance rule:

| id (prefix) | foreign project |
| --- | --- |
| `57e89f7223b0960d5ee5ea048c69e3c47e088572` | `paper-qa`, the pin |
| `42312b8d9c76ab25990cddfd76e3622276854118` | `paperspine`, the pin |
| `66b1ae3e24ffa7040ed5244490ce2872ac2e86bb` | `docx2python`, the wheel revision |
| `c692d0dfeac4a0296599f7fe21a253a58b7ac12a` | `paper-qa`, the remote tip |

## 5. What was measured

The reading below is from the tree at `c8117b9` plus this record, on
2026-11-28. The counts are a reading, not a constant: a document or a citation
added later changes them, and the floors in the witness are set below the
measured values so a scan that stopped reading falls through them.

| what | count |
| --- | --- |
| documents read | `200` |
| citations judged | `1093` |
| distinct commits cited | `436` |
| of them reachable from `HEAD`, a remote branch or a tag | `430` |
| of them unreachable, every one declared as gone | `6` |
| tree/blob citations, naming three ids (two trees, one blob) | `8` |
| SHA-256-width tokens (41+ hex) not treated as object ids | `154` |
| foreign revisions skipped, by the provenance rule | `15` citations, `4` ids |
| short tokens this checkout could not resolve, so not judged | `114` |
| findings | `0` |

The first run on the merged tree found **one** citation the rewrite had
missed: a record written after the rewrite named the commit its batch started
from under the **pre-rewrite** name. The citation was re-pointed, the record
now says the hash moved, and the diff of `94bf9b6` carries both.

## 6. The mutation check

Each mutation below was applied to the tree, the witness was run alone, the
failure message was read, and the file was restored; `git status` was clean
after every one. Only ids, paths and counts are quoted.

| mutation | the witness said |
| --- | --- |
| one digit of a full id changed (`21ea0725…cd1` → `…cd2`) | `1 citation(s) … :6: '21ea0725…cd2' names no object in this repository` |
| a tree id written where the record claims a commit (`340083a0…`) | `… :6: '340083a0…' names a tree, where the record claims a commit` |
| the foreign project's name removed from a row that pins its revision | `… LC-P2-07-fidelity-baseline.md:690: '66b1ae3e…' names no object in this repository` |
| a 64-character digest cut to 40 characters | `… G4-acceptance.md:2430: 'a1c16386…' names no object in this repository` |
| a declared absence's id changed, so the entry names nothing | `3 citation(s) … LC-P3-02-shard-anchor-incident-2026-11-17.md:20, :21, :99: 'd74ac7aa…' the commit is reachable from no branch, remote or tag` |

The green control after every restore: **17 passed** for
`tests/test_record_citations.py`.

## 7. The arms of the witness itself

The witness's mechanisms have their own arms, and no arm passes by not running:

| mechanism | arm |
| --- | --- |
| a full id that names nothing is a finding | `test_a_full_id_that_names_nothing_is_a_finding` |
| a quotation is not a claim, and prose is | `test_a_quoted_hash_is_quoted_material_and_not_a_claim` |
| a foreign revision is not ours, and an unmarked one is | `test_a_foreign_revision_is_not_a_claim_about_this_repository` |
| a 64-character digest is not a commit, a 40-character cut is | `test_a_content_digest_is_not_a_commit_citation` |
| a tree named as a tree is green; named as a commit it is a finding | `test_a_tree_named_as_a_tree_is_green_and_as_a_commit_is_a_finding` |
| `**Tree:**` is a commit field | `test_the_tree_field_names_a_commit_even_though_its_noun_is_tree` |
| a commit no branch reaches is a finding, and a reached one is not | `test_a_commit_no_branch_reaches_is_a_finding` |
| a URL to this repository is a claim | `test_a_url_to_this_repository_is_a_claim_even_without_prose` |
| a declared absence is green; an undeclared one is not | `test_a_declared_absence_is_green_and_an_undeclared_one_is_not` |
| an absence without a reason, or with a malformed id, is a fault | `test_an_absence_with_no_reason_is_a_fault` |
| the reachability scan does not see a commit no branch reaches | `test_the_reachability_scan_does_not_see_a_commit_no_branch_reaches`, against a repository built for the purpose |
| the exception list is sound and carries no dead entry | `test_every_declared_absence_says_what_is_gone_and_why`, `test_no_absence_is_declared_twice`, `test_a_declared_absence_names_something_the_repository_no_longer_has` |
| the scan reads the tree, and the catalogue parses | `test_the_scan_reads_the_records_it_claims_to`, `test_the_upstream_catalogue_is_readable` |

The witness also judges this record: it is one of the documents the scan reads,
so the ids above are subject to the same rule as every other record's.

## 8. What is still open

- **A wrong re-point to a reachable commit** is outside any existence
  witness's reach, as §3 says. Catching it needs a claim about the commit's
  content, which these records do not make in a machine-readable form.
- **A short token this checkout cannot resolve** is not judged. The rewrite
  writes full ids for the citations it moves, which is what keeps this blind
  spot from covering the failure the witness exists for.
- **Block quotes and fenced blocks are excluded.** A hash quoted from a
  command's output or a review's finding is evidence, not a claim; each
  exclusion has an arm, and the arm's other direction fails the same token in
  prose.
- **A shallow checkout skips the reachability arm**, and says so.