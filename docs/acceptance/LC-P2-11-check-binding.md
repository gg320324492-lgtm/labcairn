# LC-P2-11: binding checks to the two confirmed rules of `proj-pilot-3`

**Status: measurement done; the check wording in §4 is DRAFT and awaits a
second reader.** §1–§3 record what was measured before anything was
written; §4 is the wording the owner is asked to confirm.

- **Branch**: `claude/check-binding-pilot3-feaddf`
- **Measured at**: `eff6561` (the merge of `docs/debt-closures` into this
  branch; `git merge-base --is-ancestor bb8f8f6 HEAD` succeeds)
- **Pilot database**: `E:\labcairn-local\pilot-ws\labcairn.db`
- **Backup taken before the first write**:
  `E:\labcairn-local\pilot-ws\labcairn.db.backup.before_binding_2026-11-03`

---

## 1. The two rules, as the memory serves them

Both rules are at **version 2, `confirmed`**; version 1 of each is
`disputed`. The pilot database holds **0 rows** in `guidance_checks` and
**0 rows** in `guidance_rule_checks`, so this is the first exercise of the
check door on real material.

### 1.1 `rule-1fcc9d1a2573d7b0` v2 — one mechanism, not a list

| Field | Value |
|---|---|
| `issue_type` | `method_and_hypothesis` |
| `statement` | 在叙述除藻剂对臭氧微纳米气泡的强化机制时，不应并列罗列多个可能的机理并以「或」连接，而应删去未加论证的那一个，写明所选机理的化学作用及其与臭氧的活化关系。 |
| `context` | 在方法或机制段落中叙述硫酸铜等化学除藻剂强化臭氧微纳米气泡除藻作用的机理时。 |
| `proposed_by` / `confirmed_by` | `operator_proposal` / `owner` |

Its sources are **four** revision events, and they are two deletions and
two insertions — the mentor did not add a new sentence, they **edited one
mechanism clause in place**:

| Event | Kind | Text |
|---|---|---|
| `rv-999867b0995458ec` | `del` | 或 |
| `rv-f9ca686e41905747` | `del` | 诱导表面氢氧根离子产生自由基的能垒的变化 |
| `rv-d30278f57bec9599` | `ins` | 改成铜离子的极化 |
| `rv-86f1b8152e74b208` | `ins` | 作用，活化臭氧等 |

**What the acts do, read together.** The paragraph the mentor was editing
read, before the edit:

> …对电子跃迁（**诱导表面氢氧根离子产生自由基的能垒的变化**，**或**改成铜离子的极化**作用，活化臭氧等**）…

The mentor **deleted the conjunctive 「或」**, **deleted the unargued
alternative** (the change in the barrier for surface hydroxyl radicals),
and **kept the one mechanism that could be stated**, then spelled out its
chemical action and its relation to ozone's activation (copper ions'
polarization; activating ozone).

The rule is therefore about a **selection**: one mechanism, argued, named
with its chemistry — not a list of candidates joined by 「或」.

**What the scope says about the evidence.** The scope reads:

> Cases whose changed paragraph reads: "1、对水中气泡溃灭和自由基产生的强化机制，…". Cases whose changed paragraph could not be read: the revision under 'rv-999867b0995458ec'; the revision under 'rv-f9ca686e41905747'

**Two of the four source events have no readable changed paragraph.** The
`del` of 「或」 and the `del` of the unargued mechanism are recorded as
unreadable, so the *before* state of those two acts is not in the material
— the paragraph quoted in the scope is what remains readable around them.
This matters for §4: the check can be derived from the acts, but the acts
do not cover every case the check would decide.

### 1.2 `rule-1006b8ca1120db13` v2 — the causal chain beside the number

| Field | Value |
|---|---|
| `issue_type` | `method_and_hypothesis` |
| `statement` | 在给出气泡溃灭对除藻效果的量化结果时，不应只写「促进作用」，而应在括号或紧接的句中补出从溃灭到能量释放再到攻击藻体的因果链条。 |
| `context` | 在方法或机制段落中量化描述离子存在对气泡溃灭的促进作用时。 |
| `proposed_by` / `confirmed_by` | `operator_proposal` / `owner` |

Its sources are **two** revision events, both insertions, one minute apart
(19:24 and 19:25 UTC on 2026-07-15):

| Event | Kind | Text |
|---|---|---|
| `rv-566ce379929a90a4` | `ins` | （促进溃灭后，能量集中释放，加速 |
| `rv-a250681fef20b2c3` | `ins` | 对藻的攻击） |

**What the acts do.** The paragraph the mentor was editing read:

> …离子存在对气泡溃灭的促进作用量化**（促进溃灭后，能量集中释放，加速对藻的攻击）**，对电子跃迁（改成铜离子的极化作用，活化臭氧等）…

The mentor took the bare noun phrase 「促进作用」 and **appended a
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

Two refusals, and one of them is the project's own rule:

- **`CONFIRMER_IS_PROPOSER`** — `if confirmed_by == check.proposed_by`
  it refuses. **The proposer may not confirm their own check.** This is
  why the owner is the second reader here and this session must not
  confirm anything.
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
which is `disputed`.

**Does the next version inherit the binding? No.** The binding is a row of
its own in `guidance_rule_checks`, carrying `rule_id`, `version` and
`check_id`. A supersede writes a **new** rule row at a higher version, and
the new row names no check until somebody binds one: *the check that
decided the old words is not automatically the check that decides the new
ones, and a rewording is not a confirmation.* This is exactly the
situation the two rules are already in — v1 `disputed`, v2 `confirmed`,
and the binding that this task creates belongs to v2.

### 2.4 The negative the project holds as a rule

**A rule may name only a confirmed check.** `write_guidance_rule_check`
raises `CHECK_NOT_CONFIRMED` for any check whose state is not
`confirmed`, with the message

> the check {check_id!r} is in state {state!r}, and a rule may name only a
> check a person has confirmed

**A withdrawn rule names no check** — `bind_check` refuses that too
(`TRANSITION_NOT_POSSIBLE`).

---

## 3. The database state, before this task wrote anything

| Table | Rows |
|---|---|
| `guidance_checks` | **0** |
| `guidance_rule_checks` | **0** |

---

## 4. Draft check wording (DRAFT — not yet proposed, not yet confirmed)

> **The wording below has not been proposed.** It is shown here so that the
> second reader can read it before anything is written to the pilot
> database.

### 4.0 The identity a proposed check will carry

- **`check_id` is derived, not supplied.** `checks.py::_check_id` hashes
  `f"{question}|{pass_criterion}|{proposed_by}|{now.isoformat()}"` with
  SHA-256 and takes the first 16 hex characters, prefixed `check-`. **A
  change to the wording changes the id**, so the owner is asked to confirm
  the wording *as written*; a later rewording is a different check.
- **`proposed_by` is `model_proposal`.** This draft was written by a model
  and not by a person, and the database's own vocabulary already
  distinguishes the two: sixteen rule rows carry
  `model_proposal`/`local-user`, and the two pilot rules carry
  `operator_proposal`/`owner`. **The proposer may not be the confirmer**,
  so `confirmed_by` will be `owner` — a second reader, and not this
  session.

### 4.1 For `rule-1fcc9d1a2573d7b0` (one mechanism, not a list)

**Question**

> 稿件中叙述除藻剂强化臭氧微纳米气泡除藻作用的机理时，是否只保留了一个机理，而没有并列列出其他未经论证的可能机理？

**Pass criterion**

> 通过，当且仅当同时满足：
> (1) 该段关于强化机理的叙述只陈述**一个**机理，且该段不含以「或」「或者」「亦可能」等把多个机理并列起来的表达；
> (2) 该段写明了这个被保留的机理的**化学作用**（是什么作用、作用于什么）；
> (3) 该段写明了这个机理与**臭氧的活化**之间的关系。

### 4.2 For `rule-1006b8ca1120db13` (the causal chain beside the number)

**Question**

> 稿件在给出气泡溃灭对除藻效果的量化结果时，是否在括号内或紧接的句中写出了从溃灭到能量释放再到攻击藻体的因果链条？

**Pass criterion**

> 通过，当且仅当在给出该量化结果的位置（括号内，或与该结果紧邻的句子中）能读出下列**全部三个环节**：
> (1) 气泡**溃灭**；
> (2) **能量**在溃灭后的释放；
> (3) 该能量释放导致对**藻体的攻击**（或其加速）。

### 4.3 What the material does not earn — stated rather than manufactured

- **One paragraph, one draft, two acts.** §4 of
  `LC-P2-11-revision-distillation.md` already says this and it stands: the
  evidence is a single paragraph of a single draft, read twice. Neither
  check above is supported by a **pattern** of mentor edits; each rests on
  **one** edit.
- **Two of `rule-1fcc9d1a2573d7b0`'s four source acts have no readable
  changed paragraph** (the two deletions). The check is derived from the
  two readable insertions plus the readable paragraph around them, so the
  *before* state of the deleted clause is inferred, not read.
- **No false-positive case exists.** There is no instance where the mentor
  **left** a parallel mechanism list in place, so the check has never been
  observed to *not fire* on material the mentor chose not to touch. The
  pass criterion is therefore **not** validated by a negative case — it is
  derived from what the mentor did do.
- **The checks are decidable, but running them is the reader's work.**
  `checks.py` says so in its own words: *a check is decidable, and
  deciding it is the reader's work.* Nothing in this task runs a check
  against a draft.

---

## 5. What is still owed

- The owner confirms both checks as second reader (this session must not,
  and must not simulate one).
- `propose_check` → owner's `confirm_check` → `bind_check` at **v2**.
- Read back through `read_rule_checks` and `search_rules`.
- The negative witness: a `candidate` check cannot be bound.

---

*Nothing has been pushed. No pull request has been opened. No CI run has
been started.*
