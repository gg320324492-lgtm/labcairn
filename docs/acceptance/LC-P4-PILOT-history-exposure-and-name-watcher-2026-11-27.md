# LC-P4-PILOT — what the two name watchers actually catch, and what the published history already exposes

**Ticket:** LC-P4-PILOT (the name watchers, measured; the published-history
exposure, costed).
**Date:** 2026-11-27.
**Tree:** `3d99b07` (worktree `sad-proskuriakova-79abb4`), Windows 11 Pro
(10.0.26300 x64, AMD64), Python 3.12.13.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge, and no history rewritten. This record measures and costs; it does
not act on the published history.
**Scope:** the exposure measurements are about the **remote** refs
(`origin/main`, `origin/claude/delivery-phase5`, the `refs/pull/*` set) and
are therefore independent of the local commits this window adds; the
tree-side measurements are about the tree at `3d99b07`.

**What is claimed here.** Two things, and only those. First, the tree's two
name mechanisms, stated precisely: what each catches and what it lets past,
and the smallest gap that is closed inside the tree by a pin that fails for
that property. Second, what the published history already exposes, and the
cost of the only remedy that reaches it — handed to the owner as a choice
with measured costs, not performed.

## The two tree mechanisms, precisely

**Mechanism 1 — the longest-Han-run budget.**
`scripts/cjk_ceilings.py --json` measures, per tracked file, the **longest**
run of Han characters, and `tests/test_no_reference_leakage.py` pins those
numbers in `CJK_RUN_CEILINGS`, comparing the tree against the table in both
directions (`test_the_tree_carries_no_more_chinese_than_was_measured`). It
is a budget, not a ban: a new **long** Chinese run is an act someone
registers deliberately, in the commit that adds it.

**What it catches.** A new long Chinese run anywhere in the tree — the shape
of a quoted comment, a distilled rule statement or a manuscript paragraph.
It also catches a carried-forward number, because the pin is an equality,
not a `<=`.

**What it lets past.** A short addition that does not move the longest run.
A four-character name appended to a file whose longest run is seven leaves
`longest_run` at seven; the table is unchanged and the witness is green.
Measured against the current pin: **44** of the 56 pinned files carry a
longest run of four or more, and **49** carry one of three or more — so a
short name has a hiding place in the large majority of the files the budget
watches. This was confirmed by probe: a four-character name appended to a
file whose longest run was seven left the measurement at seven and the
witness green.

**Mechanism 2 — the zero-tolerance name watch.**
`tests/test_pilot_records_carry_no_names.py` holds the pilot's own records
to three checks: no Han character run, no fullwidth enumeration comma, and
no identifier shape a real name or affiliation leaves behind (email, phone,
grant or project number, ORCID). It is scoped to two globs —
`docs/acceptance/LC-P4-PILOT-*.md` and
`docs/acceptance/batch-*-review-*.md` — and its rule is a **ban** over that
scope: any Han character in one of those records is a failure.

**What it catches.** A name in any of the pilot's own records, of any
length, because that scope's rule is zero-tolerance rather than a budget.

**What it lets past.** A name anywhere **outside** the two globs — the
earlier acceptance records, the source files, the handoff — and, inside a
file that already carries a longer run, a name is caught only because the
rule is a ban, not because the budget sees it. The two mechanisms together
still leave the case unwatched: **a short name in a file outside the
pilot's globs, or inside a file that already carries a longer run.**

## The gap this window closes, and where the pin lives

The smallest closing is a companion pin: **the whole Han load of every
tracked file**, measured by a new `--totals` path in the same script and
pinned in a new file, `tests/test_chinese_totals_pin.py`. A name of any
length moves a file's total even when it does not move the file's longest
run, so the pin reddens in exactly the case Mechanism 1 is blind to, in a
file anywhere in the tree — not just the two globs.

The two rules are deliberately **not** merged into one place, and this is
the stated reason:

- The existing budget (`test_no_reference_leakage.py`, the longest-run
  table) keeps working as a budget: the new pin does not widen it or turn
  it into a ban. Adding a new long run still moves a longest-run value and
  still has to be registered; the two tables are independent.
- The new pin measures a **different property** (a file's whole Han load)
  over a **different scope** (every tracked file, not the two globs).
  Folding it into the longest-run file would conflate two properties and
  two scopes; folding it into the no-names file would make a global
  measurement answer to a two-glob rule. A third, single-property witness
  is the smallest honest shape, and its guard-of-a-guard demonstration
  (the mutation test that appends a shorter run to a longer one and asserts
  the longest run did **not** move while the total did) has nowhere to
  live but alongside it.

The mutation was checked to turn the new pin red: a four-character name
appended to a file that already carries a seven-character run left the
longest-run measurement unchanged and moved the total by the name's
length. A broken `--totals` that merely re-reported the longest run would
leave the total unchanged and redden instead of blessing the tree.

## What the published history carries

The repository is public; anything in its git history is anonymously
readable over plain HTTPS. Two commits hold a Chinese personal name in a
document, and both are reachable from a public ref:

| commit | date | the document | Han runs | characters | UTF-8 bytes | redacted at the tip by |
|---|---|---|---|---|---|---|
| `e67269a` | 2026-11-01 | `docs/acceptance/second-corpus-absorption.md` | 3 | 20 | 60 | `f0f9cdb` |
| `a399bfb` | 2026-11-27 | `docs/acceptance/LC-P4-PILOT-replay-2026-11-26.md` | 5 | 26 | 78 | `7fae861` |

Fetching either file at its commit over
`https://raw.githubusercontent.com/gg320324492-lgtm/labcairn/<sha>/<path>`,
with no credential, answers **HTTP 200** with the runs in the body. The
counts and byte lengths above are what was measured; the characters
themselves are not printed here, in a commit, or in any other file.

The redactions (`f0f9cdb`, `7fae861`) cleaned the **tree tips** only; the
blobs stayed in history, and history is what the remote serves. A name is
material, so this is a disclosure, not a stale tree.

**Which public refs carry the name.**

| ref | `e67269a` | `a399bfb` |
|---|---|---|
| `origin/main` | yes | no |
| `origin/claude/delivery-phase5` | yes | yes |
| `refs/pull/224/head` | yes | no |
| `refs/pull/225/head` | yes | yes |
| `refs/pull/225/merge` | yes | yes |

Of the **220** public `refs/pull/*/head` refs, two carry `e67269a`
(`#224`, `#225`) and one carries `a399bfb` (`#225`). The repository has
**0** forks today. `e67269a` is in the default branch already; `a399bfb`
is not — it reaches `main` only when pull request #225 merges.

## What a rewrite would and would not do on a public host

A rewrite makes the rewritten branch **tips** stop serving the old blobs
through refs. It does **not** erase the objects:

- Any other ref, fork, or already-cloned copy that holds the objects keeps
  them, and the remote continues to serve an object by sha while it is
  reachable from any ref.
- Cached views (the host's object cache and any CDN in front of it) persist
  past the rewrite; the host's support process for purging unreachable
  objects is the lever that reaches them, and it is the one step only the
  owner can start. It is best-effort, not guaranteed.

So a rewrite of `main` plus the delivery line removes the name from the
default branch's tips and from the delivery tip; it is the **host-side
purge** that removes the name from the internet's cached copies, and that
step is outside this window's authority.

## What a rewrite would break

A rewrite re-hashes every commit from the named commit forward, and every
tracked citation of a re-hashed commit dangles. Measured:

- **Rewriting `main` to drop `e67269a`** re-hashes **1088** commits
  (the range from `e67269a` to the `origin/main` tip), **252** of them
  merge commits. Tracked-document citations inside that range: **414**
  distinct commit ids across **126** files, the upper bound of what would
  dangle. The assertions that would redden are the **ancestor** checks —
  a "measured at" or "describes the tree at" anchor is legal only while
  the revision is an ancestor of `HEAD`, and every one of them
  (`test_status_consistency.py` holding the six "measured at" anchors
  `a29e0eb`, `384eb2f`, `109d791`, `a1f9e54`, `5446df8`, `3fcfbf6` and
  the board-cited merge commits; `test_ci_shard_coverage.py` holding the
  required-check reading revisions `6b3211a`, `69be18e`, `ac362d2` and
  the shard cost anchor) stops being satisfied. The **existence**
  checks ("cites a commit that is in this checkout") would still be
  satisfied, because the old objects stay reachable through the other
  refs — which is precisely why the host-side purge is the step that
  matters. A force-push to the protected `main` also requires the owner
  to relax branch protection, and it invalidates the open pull request
  #225.
- **Rewriting the delivery line to drop `a399bfb`** re-hashes **21**
  commits (from `a399bfb` to the `delivery-phase5` tip). Tracked
  citations inside that range: **24** across **8** files, **17**
  distinct. It would also require closing and recreating pull request
  #225 and one new run. It does **not** reach `e67269a`, which is already
  in `main`.

## A name, not a credential

What is exposed is a person's name tied to the owner's unpublished
corpus, not a key or a secret. There is nothing to rotate and no active
breach to contain. What follows:

- **Urgency is set by the disclosure's blast radius, not by a security
  incident.** The name identifies the people behind the material; the cost
  of a remedy is measured in disruption to 1088 commits, 252 merges, 126
  files and a host-side purge, not in an emergency.
- **The remedy is a deliberate choice, not an obligation.** A credential
  would be rotated the moment it leaked; a name cannot be, so the owner
  weighs whether the disclosure's impact justifies the cost of a
  history rewrite and a support request.

## Options, with the measured costs

| Option | What it does | Measured cost | What it does not do |
|---|---|---|---|
| **1. Do nothing.** | Both names stay anonymously fetchable; `a399bfb` also enters `main` when #225 merges. The tree tips and the pilot's records stay clean, and the new total-Han pin watches the tree going forward. | 0 — no commits, no refs, no run. | Reach any copy of the name. |
| **2. Rewrite the delivery line only** (drop `a399bfb` from `origin/claude/delivery-phase5`, recreate #225, request a host purge), **before** #225 merges. | The second leak stops reaching `main`; the delivery tip no longer serves the blob. | 21 commits re-hashed; 24 tracked citations in 8 files (17 distinct) re-measured; #225 closed and recreated; one new run; a host-side purge for the old objects. | `e67269a`, already in `main`, is untouched. |
| **3. Rewrite both** (drop `e67269a` from `main` and `a399bfb` from the delivery line, request a host purge). | The only option that removes **both** names from the default branch's tips. | 1088 commits re-hashed (252 merges); 414 tracked citations in 126 files re-measured (upper bound); the required-check revisions, the shard cost anchor and the six `test_status_consistency` "measured at" anchors all move; a force-push to protected `main` under relaxed branch protection; the open PR #225 closed and recreated; a host-side purge — the 220 `refs/pull/*/head` refs (nearly all merged PRs) keep the old objects reachable, so the purge is the only step that reaches them. | Erase cached or already-cloned copies outright; the purge is best-effort. |

None of these is performed here, and none is recommended as the
owner's: the record states the measured cost of each so the owner can
choose. The tree-side gap is closed regardless, by the new pin.

## What this record does not decide

It does not decide which option, if any, the owner takes. It does not
push, force-push, rewrite, delete or recreate any ref, and it does not
open a support request. It does not say the exposure is tolerable or
intolerable; it says what it costs to close and what each closing would
and would not achieve.
