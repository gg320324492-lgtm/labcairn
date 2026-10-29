# XtraGPT — upstream study

**Role in Phase 2:** reference for LC-P2-12 (the guided-revision agent) and
LC-P2-10 (edit-intent labelling). Read, not linked.

| | |
|---|---|
| **Repository** | https://github.com/Xtra-Computing/XtraGPT |
| **Pinned SHA** | `9f4be5c69878b16b5836a3769745bd190b585572` |
| **Pin method** | `git clone --filter=blob:none` of the default branch, 2026-10-29; SHA read from the local object store |
| **Paper** | *XtraGPT: Attacking LLMs with Human Feedback*, ACL 2026 — https://aclanthology.org/2026.acl-long.47/ |
| **Licence of the code** | **not declared in the tree** — see below |
| **Licence of the model** | ModelGo Zero License 2.0, **per the README's own statement** — see below |
| **Licence of the data** | not established |
| **Decision** | **study only; no weights, no data, no code** |

## The licence question, which the design flagged and the tree confirms

The design's §2 note said the repository *"is a fork; verify the upstream, the
repository/weights/data authorisations separately, and do not treat copying
weights or prompts as making it usable."* What the tree shows at the pinned
SHA:

1. **There is no `LICENSE` file.** `find . -maxdepth 3 -iname 'LICENSE*'`
   returns nothing.
2. **The README claims one anyway.** Its "Model License" section reads:

   > *"This model is released under the **ModelGo Zero License 2.0 (MG0-2.0)**.
   > MG0-2.0 is a highly permissive open model license designed to facilitate
   > the widest possible adoption and collaboration. It allows for
   > **unrestricted use, reproduction, distribution, and the creation of
   > derivative works including for commercial purposes**, without requiring
   > attribution or imposing copyleft restrictions."*

   and then: *"refer to the `LICENSE` file in the repository."*

   **There is no such file.** The README points at a licence text that the
   repository does not contain.

3. **The clone's history shows a published skill tarball as the newest
   commit** — `Add live three-way demo for xtragpt-paper-revision-skill`, with
   `xtragpt-paper-revision-skill.tar.gz` committed at the repository root.

This is three separate authorisation questions, and the design was right to
ask for them separately. The record's honest answer to each:

| What | Status | Consequence |
|---|---|---|
| **Code** | no licence file in the tree | no rights to copy the source; study only |
| **Weights** | README asserts MG0-2.0 | **unverified** — the referenced licence file is absent, and the README's summary is a paraphrase, not the licence text |
| **Data** | not established | not usable for any Phase 2 experiment |

The MG0-2.0 summary reads permissively, and it is tempting to record this as
"permissive, therefore usable". That would be exactly the mistake the
design warns about: **a paraphrase in a README is not a licence grant, and a
licence that is asserted but not shipped cannot be complied with.** The
attribution clause, if MG0-2.0 has one, cannot be honoured against a licence
text nobody can read. MG0-2.0 also has its own terms about model
derivatives and use, which a paraphrase of "unrestricted use" does not
convey.

**The decision is therefore: no weights are downloaded, no prompts are
copied, and the tarball at the repository root is not extracted or run.**
Nothing from this repository is used as an input to any Phase 2 measurement.

There is a further reason, independent of licensing, and it is the one the
Phase 2 data rules care about most: the weights are **trained on academic
paper revision pairs**, which means the training corpus is third-party
scientific writing. Using those weights in a project whose entire thesis is
*"the agent must learn from verifiable, attributable revision histories"* would
import an **unattributable** prior. A guidance system whose weights already
encode unlabelled revisions cannot claim that its advice comes from the
导师经验库 the design specifies, and it cannot report which parts of its
behaviour are learned and which are inherited. That is a scientific-integrity
argument, not only a licensing one, and it is the stronger of the two.

## What the tree contains

| Path | What it is |
|---|---|
| `train/`, `configs/`, `requirements.txt` | the training pipeline and its configuration |
| `paper_revision_bench/` | the benchmark |
| `full_paper_evaluation/`, `6_component_evaluation/` | the evaluations |
| `xtragpt-paper-revision-skill/` and `.tar.gz` | a packaged "paper revision skill" |
| `scripts/`, `tests/`, `examples/` | supporting material |

The structure worth studying is the **skill package** — it is an attempt at
the same shape Phase 2 wants: a packaged procedure for revising a paper.
That is directly comparable to LabCairn's own `research-report` Skill
(LC-P1-07), and comparing the two is worth doing at LC-P2-12's design time.

## How well it fits the mentor-trajectory question

**The conceptual fit is strong, and the data fit is absent.**

XtraGPT's premise — that revision quality depends on *what the instruction
asks for* and *what context the model is given*, not on the model's
generality — is very close to what Phase 2 is trying to do with the
advisor's actual instructions. Its "context-sensitive, instruction-aligned
revision" framing is a direct parallel to the design's
*问题 → 指导意见 → 修改行动* chain, and its component-wise evaluation is a
model for how Phase 2 should report its own results (§7 of the design lists
several dimensions that a component-wise report would cover naturally).

But the input it learns from is **paper text and an instruction**, not
**a traced revision history**:

| Phase 2 needs | XtraGPT provides | Gap |
|---|---|---|
| instruction-conditioned revision | yes — the core contribution | — |
| component-wise evaluation | yes | the report shape to borrow |
| the advisor's identity and role | no | — |
| what the advisor actually changed, and why | no | it learns from final pairs |
| the student's response and whether it worked | no | no outcome signal |
| the reviewer's later reaction | no | — |
| attributable, sourced experience | no | the central gap |

So the same verdict as for arXivEdits, in a different register: XtraGPT
demonstrates that **instruction-conditioned revision is learnable and
measurable**, which is the design's core scientific premise, and it
demonstrates it **without** the trajectory data that Phase 2 says is the
source of the value. That is a *supporting* result for Phase 2's thesis and
a *threat* to it at the same time: if instruction-conditioned revision works
from paper pairs alone, then a Phase 2 ablation showing no gain over
"current draft + general LLM" would not be a failure of implementation — it
would be evidence that the trajectory does not carry the value the design
assumes. **The ablation is therefore not optional, and XtraGPT is the reason
the comparison must be run rather than argued.**

## Two readings the design already makes, confirmed

**On multi-agent systems.** The design says Phase 2 should not begin with a
complex multi-agent deployment, and that SWIF²T's planner/investigator/
reviewer/controller split is a *reference*, not a template. XtraGPT's
`6_component_evaluation` is the same kind of artefact: a multi-component
system whose value is in the *evaluation decomposition*, not in the number of
components. LabCairn already has the decomposition it needs — Stage, Operation,
Approval, EvidenceLedger, and the refusal vocabulary — so adopting a
component taxonomy would be a second vocabulary for things that already have
one. The project's own history records what happens when two work orders each
introduce a vocabulary: LC-P1-03's two capability vocabularies, and the
source id's type in G4. **Phase 2 does not adopt a component taxonomy; it
reuses ADR-0006's capability registry.**

**On the evaluator.** The design notes that LLM judges are useful for
instruction-following and limited for scientific correctness, and that the
final evaluation must combine human scientific judgement with verifiable
data. XtraGPT's evaluation is a good example of the thing the design warns
against: an automated comparison of revision quality against a reference
revision. Whether its benchmark scores are model-judged or reference-diffed
was **not determined** by reading the tree at this depth, and it is recorded
here as an open question rather than as a finding.

## What is decided, and what is not

**Decided:**

- Study only. No weights downloaded, no code copied, no tarball extracted or
  run, no dataset ingested.
- The licence position is recorded as **"asserted in prose, not shipped in
  the tree"** — not as "permissive". Anyone who wants to use this must obtain
  the licence text and the data licence directly, and that is the owner's
  decision, not this project's.
- The `paper_revision_bench/` is **not** used as Phase 2's evaluation set.
  It is a published benchmark; Phase 2's own protocol (LC-P2-14) requires a
  frozen held-out set split **by paper**, and reusing an external benchmark
  for the headline ablation would import that benchmark's split decisions.

**Not decided:**

- Whether the *ideas* in the skill package are compatible with LabCairn's
  `research-report` Skill contract, or whether the two should be unified at
  LC-P2-12's design time. The comparison has not been made.
- Whether XtraGPT's evaluation protocol is a sound model for LC-P2-14's
  ablation, and specifically whether its component decomposition should
  influence Phase 2's reporting dimensions. Open until the evaluation code
  is read at the pinned SHA.
