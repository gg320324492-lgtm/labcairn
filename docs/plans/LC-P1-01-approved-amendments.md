# LC-P1-01 — Approved amendments (binding decisions)

**Status:** Approved design decisions, **not implementation**.  
**Date:** 2026-10-15 · **Subject:** `623e3ca31caba327d2f8b1af40ab67c35c7a61d3`.  
**Review:** [LC-P1-00 formal review](../acceptance/LC-P1-00-review-623e3ca.md).

These C-1–C-8 decisions supersede contradictory instructions in `docs/UPSTREAM_REFERENCES.md`, `docs/PHASE_1_WORKORDERS.md`, and `docs/plans/LC-P1-01-task-breakdown.md`. **Synchronize those files before implementing relevant steps.**

| Conflict | Approved resolution |
|---|---|
| **C-1** | Every required `pull_request` status workflow must run without `paths-ignore` that could leave required checks pending. Optional/push workflows may filter. |
| **C-2** | Use Hatchling, with `[tool.hatch.build.targets.wheel] packages = ["src/labcairn"]`. This is an explicit recursive package root, **not** a setuptools leaf-package list; configure sdist exclusions and test actual wheel/sdist members and clean imports. No `MANIFEST.in`. |
| **C-3** | Allow LC-P1-01 to introduce minimal pure `Known / Unknown / UsageValue / UnknownReason` for FakeProvider. Leave concrete provider probes, adapters and budget controls to LC-P1-03. |
| **C-4** | Git-mode secret scanning covers all **tracked** files. Do not broadly allowlist reference trees; if mistakenly tracked, they must still be scanned. |
| **C-5** | Add `.gitattributes` to normalize LF text and declare binary files, with justified Windows script exceptions; verify hashes from fresh checkout. |
| **C-6** | Python lint/type/test CI on Ubuntu and Windows; Web initially can run on Ubuntu. This is not a real Windows application smoke test. |
| **C-7** | Create `src/labcairn/core/__init__.py` and validate it is in the installed wheel; don't prelist non-existent future packages. |
| **C-8** | Verify ignore and packaging behavior with `git check-ignore`, `git ls-files`, archive member lists and installed imports, not text matching on `.gitignore`. |

### Corrected starter packaging example

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/labcairn"]
```

## Additional gates before LC-P1-01 implementation

1. Fix ADR-0003's event seq and Task/Run ID contracts as described in the formal review, **before** generating persistent schemas.
2. Fix and test the reference checkout helper's invalid JSON and checkout-root guard.
3. Retain tracked-file secrets scanning with no broad excluded-path allowlist.
4. No PyMuPDF dependency or publication under MIT without a documented licensing/ownership decision. A placeholder such as `LICENSE.PENDING.md` **does not grant open-source rights**.
5. Existing `623e3ca` is already the initial commit. Do not repeat T01's first-commit step.
6. Verify that clean build/CI does not require the sibling `labcairn-upstreams` checkout; FakeProvider-only behavior must not be presented as real-provider evidence.

## GitHub is the authority for project work

Create and maintain `docs/README.md` (document index), `docs/plans/` (work orders), `docs/adr/` (architecture decisions), `docs/acceptance/` (commit-specific acceptance reports), and `docs/handoff/` (short current-state continuation summary). Each report records subject commit SHA, real test commands/CI URLs, confirmed and unverified items, blockers, and next work order.

**Next review:** submit a fixed LC-P1-01 implementation commit/PR with actual two-OS CI results, reference-free wheel/sdist, clean-room installation, FakeProvider truthfulness tests and updated authoritative documents. No LC-P1-02 implementation before that review.
