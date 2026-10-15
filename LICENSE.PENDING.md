# Licensing status: PENDING — no rights granted

**This file is not a license. It is a notice that no license has been granted.**

**Version:** LC-P1-v1.1 · **Updated:** 2026-10-15 · **Status:** undecided

---

## 1. No open-source rights have been granted

**Nothing in this repository is licensed to you.** No permission to use, copy,
modify, publish, sublicense or redistribute LabCairn source has been granted to
anyone. Copyright ownership has not been cleared, so there is no licensor
capable of making a grant. Until that is settled, the repository is
**all-rights-reserved by default**.

This applies to every file in the repository — source, tests, documentation,
ADRs, configuration and assets — except where a file carries an explicit,
third-party license header. Those remain under their own terms.

## 2. This placeholder grants nothing and must not be read as MIT

**This file is not an MIT license, not an MIT offer, and not evidence of an
intention to license under MIT.** A file named `LICENSE.PENDING.md` is not
`LICENSE`. Neither GitHub nor PyPI nor any downstream tooling treats it as a
license grant, and neither should you.

Concretely, do **not**:

- read this file as a grant of permission to use the code;
- state or imply that LabCairn is "MIT licensed", "open source" or
  "permissively licensed" in a dependent project, a paper, a submission or a
  derived work;
- vendor, fork, sublicense or redistribute LabCairn on the strength of it;
- treat the absence of a restrictive `LICENSE` file as permissiveness. Silence
  is not permission.

The intended direction below is a **plan**, not a promise and not a grant.

## 3. Why no `LICENSE` file exists

The project lead made an explicit decision (LC-P1-01 §8, binding): **ownership
is not clarified, therefore no `LICENSE` file is added.** A file named `LICENSE`
carries a legal meaning that placeholder text would falsify — GitHub would render
it as the project's license, PyPI classifiers would cite it, and forks would
inherit a claim that was never made. A deliberately misnamed placeholder is the
honest form of the same statement.

## 4. Intended licensing direction (a plan, not a grant)

**Planned:** MIT, for original LabCairn code, contingent on all conditions in §5.

Rationale: the project is a research workbench intended for academic and
independent use, and MIT is the most permissive license compatible with that
intent. It is also the license already carried by four of the five upstream
reference projects studied in LC-P1-00.

## 5. Conditions that must ALL hold before `LICENSE` is written

1. **Copyright ownership of all LabCairn source is settled.** This is the
   blocking item. Until it is, there is no party that can grant a license.
2. **The dependency set is final enough for a real dependency review.** A
   release cannot be MIT in name while shipping a component whose own license
   forbids it.
3. **`PyMuPDF` is resolved.** See §6 — this is the specific risk to the MIT plan.
4. **ADR-0004's AGPL-3.0 boundary is confirmed un-crossed** by the final
   dependency graph.
5. **`LICENSE.PENDING.md` is deleted in the same commit that adds `LICENSE`.**
   Both files must never coexist; a lingering placeholder after a grant is
   itself a misleading state.

## 6. PyMuPDF — the unresolved blocker

**`PyMuPDF` is licensed AGPL-3.0 / commercial dual-license.** There is no
unencumbered MIT grant of it.

`PyMuPDF` is named by **LC-P1-08** (material inventory and source locators) as
the text-PDF parsing dependency. LC-P1-08 is recorded in
`docs/PHASE_1_WORKORDERS.md` as **NOT STARTED — blocked on a licensing
decision**, and that decision has not been made.

Why this constrains an MIT release:

- If LabCairn ships or links `PyMuPDF`, an MIT grant over LabCairn's own code
  does **not** make the combined work MIT. The AGPL obligations attach to the
  combined work.
- AGPL-3.0 is the strongest copyleft in common use: linking to it as a library
  obliges offering complete corresponding source of the combined work to network
  users.
- So the choice is not "MIT, and note PyMuPDF in a NOTICE". The choice is
  between **not depending on PyMuPDF**, **purchasing a commercial license**, or
  **re-licensing the affected distribution** — and that decision belongs to the
  project lead, not to this file.

Related: `docs/adr/ADR-0004` records that `packages/paper-qa-pymupdf/` in the
reference project `paper-qa` is **AGPL-3.0** while the `paper-qa` root and its
other subpackages are Apache-2.0. Rejecting that subpackage is what currently
keeps an AGPL component out of LabCairn's dependency graph. See
`docs/UPSTREAM_REFERENCES.md` § "Verified license boundaries".

## 7. CI must not fail for the absence of a `LICENSE`

**No CI job in this repository asserts the presence of a `LICENSE` file.**
Any such check would have to be one of:

- *fail until the file exists* — permanent red CI that trains people to ignore
  the signal;
- *pass unconditionally* — asserts nothing;
- *check this file's text* — locks in a fiction.

All three are worse than no check. Until ownership is cleared there is nothing
for a machine to assert. **The real gate is LC-P1-14's license/NOTICE audit**
(G5), where ownership is actually settled and a real `LICENSE` can be written.

## 8. What you may rely on today

- LabCairn source is **all-rights-reserved**. Read it; do not redistribute it.
- Third-party material, if and when any is adapted in, keeps **its own** license
  and required notices. Adapting MIT code into a repository with no license does
  not relicense it, and does not grant you anything.
- LabCairn is independently developed and is **not affiliated with** OpenHands,
  Pydantic AI, Deep Agents, PaperQA2 or PaperSpine.

---

**Status:** pending · **Owner:** project lead · **Closes at:** LC-P1-14 (G5)
