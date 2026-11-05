# LC-P2-11: a check bound to each of the two confirmed rules of `proj-pilot-3`

**Status: the binding is done and verified.** Each of the two rules the
owner confirmed on 2026-11-03 now names a check — a question a reader can
run against a manuscript, and the criterion that says what passes. **This
file is the record of it.**

**This branch touches this file and nothing else.** The closure pointer
in §6.5 of `LC-P2-11-revision-distillation.md` is the parent session's to
write, and that file is **not** modified here.

- **Branch**: `claude/check-binding-pilot3-feaddf`
- **Measured at**: `991c063` (the merge of `docs/debt-closures` into this
  branch; `git merge-base --is-ancestor bb8f8f6 HEAD` succeeds)
- **Pilot database**: `E:\labcairn-local\pilot-ws\labcairn.db`

**The backups, and how each is known to predate the write.** All three
hold **0 rows** in `guidance_checks` and **0** in `guidance_rule_checks`,
which is what makes each of them evidence of the state before the
binding:

| Backup | Taken by | State it holds |
|---|---|---|
| `E:\labcairn-local\pilot-ws\labcairn.db.backup.before_binding_2026-11-03` | this session, before the write | 0 checks, 0 bindings |
| `E:\labcairn-local\revdistil-pilot3\labcairn.db.before` | the parent session | 0 checks, 0 bindings |
| `E:\labcairn-local\revdistil-pilot3\labcairn.db.before-v2` | the parent session | 0 checks, 0 bindings |

---

## 1. What the two rules are, and what they rest on

Both rules are at **version 2, `confirmed`**; version 1 of each is
`disputed`.

### 1.1 `rule-1fcc9d1a2573d7b0` v2 — one mechanism, not a list

| Field | Value |
|---|---|
| `issue_type` | `method_and_hypothesis` |
| `statement` | **the words are not carried here** (removed 1 fragment: 76 characters sha256 `11dee2520513`); the row is `rule-1fcc9d1a2573d7b0` v2 in the store |
| `context` | **not carried here** (removed 1 fragment: 37 characters sha256 `68e5359047c9`) |
| `proposed_by` / `confirmed_by` | `operator_proposal` / `owner` |

Its sources are **four** revision events, and they are two deletions and
two insertions — the mentor did not add a new sentence, they **edited one
mechanism clause in place**:

| Event | Kind | Text |
|---|---|---|
| `rv-999867b0995458ec` | `del` | the conjunction; **not carried here** (removed 1 fragment: 1 character sha256 `a2123d69506f`) |
| `rv-f9ca686e41905747` | `del` | the unargued mechanism clause; **not carried here** (removed 1 fragment: 20 characters sha256 `e7749feb3f64`) |
| `rv-d30278f57bec9599` | `ins` | the replacement naming the mechanism; **not carried here** (removed 1 fragment: 8 characters sha256 `f854a5ad4b7d`) |
| `rv-86f1b8152e74b208` | `ins` | what it is said to do; **not carried here** (removed 1 fragment: 8 characters sha256 `512f50f9dcf0`) |

**What the acts do, read together.** The paragraph the mentor was editing
read, before the edit:

> **the paragraph is not reproduced** (removed 5 fragments: 5 characters sha256 `bce4d290fbb5`, 20 characters sha256 `e7749feb3f64`, 1 character sha256 `a2123d69506f`, 8 characters sha256 `f854a5ad4b7d`, 8 characters sha256 `512f50f9dcf0`): the span carries the deletion and the two insertions above, and the store holds it under the four `rv-` addresses

The mentor **deleted the conjunction**, **deleted the unargued
alternative** (the change in the barrier for surface hydroxyl radicals),
and **kept the one mechanism that could be stated**, then spelled out its
chemical action and its relation to ozone's activation (copper ions'
polarization; activating ozone).

The rule is therefore about a **selection**: one mechanism, argued, named
with its chemistry — not a list of candidates joined by a conjunction.

**What the scope says about the evidence.** The scope records that **two
of the four source events have no readable changed paragraph** — the `del`
of the conjunction and the `del` of the unargued mechanism. The paragraph quoted in
the scope is what remains readable around them, so the *before* state of
those two acts is inferred, not read. §5 says what that costs.

### 1.2 `rule-1006b8ca1120db13` v2 — the causal chain beside the number

| Field | Value |
|---|---|
| `issue_type` | `method_and_hypothesis` |
| `statement` | **not carried here** (removed 1 fragment: 62 characters sha256 `b3714d253a83`); the row is `rule-1006b8ca1120db13` v2 in the store |
| `context` | **not carried here** (removed 1 fragment: 28 characters sha256 `44189305dd1e`) |
| `proposed_by` / `confirmed_by` | `operator_proposal` / `owner` |

Its sources are **two** revision events, both insertions, one minute apart
(19:24 and 19:25 UTC on 2026-07-15):

| Event | Kind | Text |
|---|---|---|
| `rv-566ce379929a90a4` | `ins` | the opening of the causal chain; **not carried here** (removed 1 fragment: 15 characters sha256 `9f78fd828023`) |
| `rv-a250681fef20b2c3` | `ins` | its closing; **not carried here** (removed 1 fragment: 5 characters sha256 `28fd872a9eeb`) |

**What the acts do.** The paragraph the mentor was editing read:

> **the paragraph is not reproduced** (removed 3 fragments: 16 characters sha256 `7b66b38aa980`, 20 characters sha256 `2a329f43b90b`, 22 characters sha256 `b2ea1cf6cd52`): the span where the parenthetical chain was inserted, held by the store under the two `rv-` addresses above

The mentor took the bare noun phrase for the enhancement and **appended a
parenthetical that spells the chain**: bubble collapse → energy released
in concentration → accelerated attack on the algae. The rule is about
**spelling the chain where the number is given**, not about restating the
number.

---

## 2. What the doors actually do (measured from the source, not assumed)

### 2.1 `propose_check` — what it requires

`src/labcairn/guidance/checks.py` → `propose_check(context, *, question,
pass_criterion, proposed_by, now)`. The row it writes carries `question`,
`pass_criterion`, `state`, `proposed_by`, `confirmed_by` and
`resolution_reason`; the row starts in state **`candidate`**.

### 2.2 `confirm_check` — what it refuses

- **`CONFIRMER_IS_PROPOSER`** — `if confirmed_by == check.proposed_by`
  it refuses. **The proposer may not confirm their own check.**
- The check must exist, and it must be a `candidate` — the closed state
  machine is the layer's, so `confirm_check` asks the layer rather than
  restating it.

### 2.3 `bind_check` — which version it attaches to

`src/labcairn/application/guidance.py` → `write_guidance_rule_check(context,
*, rule_id, check_id)`:

```python
row = _latest(context, rule_id)          # <- the rule's HIGHEST version
check = read_guidance_check(context, check_id=check_id)
if check.state != "confirmed":
    raise guidance_refused(
        GuidanceRefusal.CHECK_NOT_CONFIRMED,
        ...
    )
```

and `_latest` is:

```python
select(GuidanceRuleRow)
    .where(GuidanceRuleRow.rule_id == rule_id)
    .order_by(GuidanceRuleRow.version.desc())
    .limit(1)
```

**So the binding lands on the rule's highest version.** For both rules
here that is **version 2** — the `confirmed` one — and not version 1,
which is `disputed`. The pilot rules were already in the situation that
makes this observable: v1 `disputed`, v2 `confirmed`, and the bindings
below are on **v2**.

**Does the next version inherit the binding? No.** The binding is a row of
its own in `guidance_rule_checks`, carrying `rule_id`, `version` and
`check_id`. A supersede writes a **new** rule row at a higher version, and
the new row names no check until somebody binds one: *the check that
decided the old words is not automatically the check that decides the new
ones, and a rewording is not a confirmation.*

### 2.4 The negatives the project holds as rules

- **A rule may name only a confirmed check.** `write_guidance_rule_check`
  raises `CHECK_NOT_CONFIRMED` for any check whose state is not
  `confirmed`.
- **A withdrawn rule names no check** — `bind_check` refuses that too
  (`TRANSITION_NOT_POSSIBLE`).

---

## 3. The checks, as the pilot database holds them

Both are **`confirmed`**, proposed by `operator_proposal` and confirmed by
`owner` — the same second-reader rule the memory applies to a rule, with
the same reading: the revision channel's proposer is a person reading the
mentor's revisions.

| Check | Bound to | Version | State |
|---|---|---|---|
| `check-a1de7d4db9d7cbda` | `rule-1fcc9d1a2573d7b0` | **2** | `confirmed` |
| `check-5df4997384d6a0bd` | `rule-1006b8ca1120db13` | **2** | `confirmed` |

### 3.1 `check-a1de7d4db9d7cbda` — for the mechanism rule

**question**

> **the check's question, `check-a1de7d4db9d7cbda`, is not carried here** (removed 1 fragment: 37 characters sha256 `3b666b1424b7`)

**pass_criterion**

> **its pass criterion is not carried here** (removed 1 fragment: 48 characters sha256 `b0a006455999`)

### 3.2 `check-5df4997384d6a0bd` — for the causal-chain rule

**question**

> **the check's question, `check-5df4997384d6a0bd`, is not carried here** (removed 1 fragment: 27 characters sha256 `a10c6a70443f`)

**pass_criterion**

> **its pass criterion is not carried here** (removed 1 fragment: 45 characters sha256 `e86a8efb401e`)

**A check is two fields, and neither may be empty.** The question is what
the reader runs; the criterion is the condition under which the answer is
yes. Neither of these restates the rule: the rule says what the advisor
demands, and the check says what a reader looks at in a draft and what
counts as passing.

**`check_id` is derived, not supplied.** `checks.py::_check_id` hashes
`f"{question}|{pass_criterion}|{proposed_by}|{now.isoformat()}"` with
SHA-256 and takes the first 16 hex characters, prefixed `check-`. A
change to the wording changes the id — so the wording above and the id
above are one fact, not two.

**The timestamps are one fixed instant.** Both checks carry
`proposed_at = confirmed_at = 2026-11-03T18:00:00+00:00` — a single
chosen moment rather than two wall-clock readings, so that a re-run of
the same proposal is the same row. The state machine is unaffected: a
check proposed and confirmed at the same instant has still been through
two readers.

**And that instant is after the event it dates.** The write landed at
**05:07 UTC** on 2026-11-03, so the stored value sits roughly twelve and a
half hours in the future. Fixing the instant buys idempotence and buys it
*at the cost of the column meaning what its name says* — a reader who takes
`proposed_at` as when the proposal happened is shown a moment that had not
arrived yet. It is left in place, because the memory does not rewrite its
past, and it is marked here, because that rule is not a licence to leave a
misleading value unmarked.

**And the fixed instant is load-bearing, which is the honest trade.**
`check_id` is derived from `question | pass_criterion | proposed_by | now`,
and the only uniqueness the table carries is that primary key — a measured
fact, not a guess: `guidance_checks` has one index,
`sqlite_autoindex_guidance_checks_1` on `check_id`, and none on `question`
or `pass_criterion`. So **writing these two rows twice against the wall
clock would create two checks with the same words**, both bindable, and the
memory would hold two rows answering one question. The moment is fixed to
prevent exactly that; the cost is that `proposed_at` stops being a time.
**A later write should keep the idempotence and drop the lie** — bind the
instant to the draft rather than to the wall clock, so a re-run is the same
row *and* the column means what its name says.

**Closed 2026-11-03 at `437987b`.** Both mint doors — `_rule_id` and
`_check_id` — now derive from the **whole draft**, length-prefixed so no field
boundary can shift, with **no instant in the digest**; and the proposal doors
**read before they write**, so a re-run of one draft returns the row already in
the memory. `proposed_at` is the real clock from here on. Measured on the real
pilot rows: **20 rule rows give 20 distinct new keys and 0 collisions**, the 2
checks likewise, and the new derivation reproduces **0 of 20** stored ids.

**And the migration boundary is stated rather than smoothed.** The 20 rules and
2 checks already in the pilot database were minted under the old formula, which
folded a chosen instant, so the new derivation **cannot reproduce those ids**
(0/20, measured). A re-run of one of those historical distillations — same
draft, same sources — would not find the stored row under the new id and would
write a **sibling** under a new id: two rows answering one question, at the
seam between the two formulas. **That is a consequence for rows already in the
memory, not a property of the new door**; the pilot database is read-only here
and untouched.

**For an operator who needs to pair an old row with its draft**, both ids are
computable from stored bytes and neither needs the memory to change: the
pre-change id is `sha256(f"{issue_type}|{statement}|{proposed_by}|"
f"{stored proposed_at.isoformat()}")[:16]` under the `rule-` / `check-`
prefix, and the new id is the length-prefixed digest of the whole draft. **A
content lookup was considered and rejected**: the layer exposes only
highest-version reads, and the two pilot rules sit at v2 with a different
statement from their v1 draft, so a content lookup against highest versions
would miss exactly the rows this note is about — finding v1 needs a
by-(id, version) content read the layer does not expose, which is a different
design and not a fix.

---

## 4. The verification

Everything below was measured through the **product's own doors**, on the
pilot database, with the worktree's `src` first on `PYTHONPATH`:

```
checks module : E:\LabCairn\.claude\worktrees\check-binding-pilot3-feaddf\src\labcairn\guidance\checks.py
```

### 4.1 Read back — the binding is at v2

```
read_rule_checks(rule-1fcc9d1a2573d7b0): 1
  check_id      : check-a1de7d4db9d7cbda
  state         : confirmed
  proposed_by   : operator_proposal
  confirmed_by  : owner
    <- bound to rule-1fcc9d1a2573d7b0 v2 (confirmed)

read_rule_checks(rule-1006b8ca1120db13): 1
  check_id      : check-5df4997384d6a0bd
  state         : confirmed
  proposed_by   : operator_proposal
  confirmed_by  : owner
    <- bound to rule-1006b8ca1120db13 v2 (confirmed)
```

### 4.2 Read back — the card carries the question

`search_rules` serves a rule with its checks inside the rule, so the
retrieval card now carries the runnable question:

```
query='<the mechanism term, not carried: removed 1 fragment: 2 characters sha256 `671fb59d9d0d`>'  -> rule-1fcc9d1a2573d7b0 v2
    check check-a1de7d4db9d7cbda [confirmed]
      Q: *(the question of `check-a1de7d4db9d7cbda`, not carried here)*
query='<the collapse term, not carried: removed 1 fragment: 2 characters sha256 `f107621fc60c`>'  -> rule-1006b8ca1120db13 v2
    check check-5df4997384d6a0bd [confirmed]
      Q: *(the question of `check-5df4997384d6a0bd`, not carried here)*
```

**Both rules are served at version 2**, which is the version that carries
the binding — the disputed v1 is not what a card shows.

### 4.3 The negative — a candidate check cannot be bound

Measured **on a copy of the pilot database**, so that the live database
gained no row nobody confirmed:

```
proposed a candidate on the COPY: check-5b03568174f6ec99 (state=candidate)

trying to bind candidate 'check-5b03568174f6ec99' to 'rule-1fcc9d1a2573d7b0'
  REFUSED, as it must be:
  application refused (guidance_check_not_confirmed): the check
  'check-5b03568174f6ec99' is in state 'candidate', and a rule may name only
  a check a person has confirmed

  the rule still names 1 check(s): ['check-a1de7d4db9d7cbda']
```

**And the live database was not touched:**

```
  candidate rows in the live database: 0
  total rows in the live database:     2
  binding: rule-1fcc9d1a2573d7b0 v2 -> check-a1de7d4db9d7cbda
  binding: rule-1006b8ca1120db13 v2 -> check-5df4997384d6a0bd
```

The refusal came **before** the binding was written, so the rule kept its
one confirmed check and nothing was left half-written. This is the
project's own rule ("a rule may name only a confirmed check"), and it is
witnessed in the suite as well by
`tests/test_guidance_rules.py::test_a_rule_may_name_only_a_confirmed_check`.

**The parent session made the same measurement independently, and earlier.**
Its negative was taken **before the confirmation** — the binding was
attempted against a candidate and refused twice, with the reason arriving
as the application-layer enum `ApplicationRefusal`, value
`guidance_check_not_confirmed`; the binding succeeded only after the
confirmation. **The two measurements are independent and agree**: the
refusal is the door's, and it does not depend on which session asks.

**Those two witnesses were run against this branch's `src`**, with the
worktree first on `PYTHONPATH` and a `--basetemp` outside the repository:

```
pytest tests/test_guidance_rules.py -k "may_name_only_a_confirmed_check or names_the_checks_that_decide_it"
2 passed, 22 deselected in 1.61s
```

---

## 5. What the material does not earn — stated rather than manufactured

- **One paragraph of one draft.** §4 of
  `LC-P2-11-revision-distillation.md` says this and it stands: the
  evidence is a single paragraph of a single draft, read a few times.
  Neither check rests on a **pattern** of mentor edits; each rests on
  **one** edit.
- **Two of `rule-1fcc9d1a2573d7b0`'s four source acts have no readable
  changed paragraph** — the two deletions. The check is derived from the
  two readable insertions plus the readable paragraph around them, so the
  *before* state of the deleted clause is inferred, not read.
- **No false-positive case exists for either check.** There is no instance
  where the mentor **left** a parallel mechanism list in place, and none
  where they left the bare enhancement noun in place. So neither pass criterion
  has been observed to *not fire* on material the mentor chose not to
  touch: **the criteria are derived from what the mentor did do, and are
  not validated by a negative case.**
- **The checks are decidable, but running them is the reader's work.**
  `checks.py` says so in its own words: *a check is decidable, and
  deciding it is the reader's work.* Nothing in this task runs a check
  against a draft, and no claim is made about any manuscript's compliance.
- **The statements name this paper's chemistry** (§6.5 of the distillation
  record) and so do the checks. They are usable by a reader of *this*
  group's manuscripts and are not a general writing standard.

---

## 6. Provenance — who wrote what

**This session did not write to the pilot database.** The session assigned
this task was interrupted repeatedly and lost its turn each time; the
parent session (this conversation) therefore carried out the
proposal, the owner's confirmation and the binding itself, at
2026-11-03 13:07 local time, while this branch measured the doors and
drafted the wording for the owner's second reader.

What this session is responsible for, and what this file records:

- **the measurement** of what each door does and refuses (§2), read from
  the source and confirmed against the live database;
- **the verification** of the binding through the product's own doors
  (§4) — the read-back, the retrieval card, and the negative witness;
- **this file**, which is the record. **The closure pointer in §6.5 of
  `LC-P2-11-revision-distillation.md` belongs to the parent session**,
  and this branch does not modify that file.

**Two drafts of the wording existed.** This session drafted a longer
wording and handed it to the owner for confirmation. The wording in §3 is
the one the owner confirmed and the database holds; the longer draft was
**not** written to the database and is **not** a second check. **Writing
it would have been the harm the parent session named**: a rule names one
check at its highest version, and a second one there would give the same
rule two names for the same question.

**`proposed_by` differs between the two drafts.** The rows in the
database carry `operator_proposal`, which is the parent session's
judgement — the revision channel's proposer is a person reading the
mentor's revisions. This session's own draft would have carried
`model_proposal`, because that draft was written by a model. **Only the
database's rows exist**, so the difference is a difference between two
drafts and not between two rows.

---

## 7. What was not done

- **The pilot database was not written by this session.** The read-back
  and the negative were the only things done against it, and the negative
  was done against a **copy** so that the live database gained no row
  nobody confirmed. The database's two checks and two bindings are the
  parent session's work.
- **Nothing pushed. No pull request opened. No CI run started.**
- `docs/RELEASE-NOTES.md`, `docs/ROADMAP.md` and every `LC-P2-07*` file
  were **not touched** — another window was writing them.
- **`docs/acceptance/LC-P2-11-revision-distillation.md` was not
  modified** in the state this branch now carries. A closure pointer for
  §6.5 was drafted here and **reverted** so that this branch and the
  parent session do not write the same file; the draft survives in commit
  `f9a16b5` of this branch if it is wanted.
- **No product code under `src/` was changed.** No missing door and no
  wrong behaviour was found: `bind_check` attaches to the highest version
  as the project requires, and an unconfirmed check is refused as the
  project requires.
- **No new test file was created.** The negative already has a witness in
  `tests/test_guidance_rules.py`, and the pilot run above measures the
  same property on real material.

---

## 8. The third rule's check — 2026-11-05

The one rule that was still a `candidate` (`rule-fea4dea2b16b6759`,
`data_quality`) was confirmed by the owner and given a check. The check was
drafted by a model (`model_proposal`), confirmed by the owner as the second
reader, and bound to the rule's **version 1** — the rule's only version.

**The wording is not carried here.** The rule and its check are written in
the material's language, Chinese; this repository's records are English, and
the check row in the pilot store is the authority. Its id,
`check-8da62cd8c2c07837`, is derived from the wording, the proposer and the
instant, so the id and the wording are one fact.

**The negative, measured on the real rows.** The bind was attempted while
the check was still a `candidate` and was refused as
`guidance_check_not_confirmed`; the real bind ran only after the
confirmation. The order is the witness, not an assertion.

**Read back.** The rule is `confirmed` at v1; the check is `confirmed` by
`owner`; one binding decides the rule at v1. The store now holds 27 rule
rows (25 `confirmed`, 2 `disputed` v1 rows superseded by their v2), 25
checks — all `confirmed` — and 25 bindings.

**The backup and the operator script.** The database was copied before the
run to `E:\labcairn-local\checkbind-pilot4\labcairn.db.before_20261105T084935Z`
(sha256 prefix `8d37ca218d997430`); the script that made the writes is
`E:\labcairn-local\bind_candidate_check.py`. Both live outside this
repository.

**What this is.** One more rule now names a confirmed check. The served face
is read through the binding, so this rule can be served the same way the
other 24 are; a retrieval card for it is the next check, not part of this
write.
