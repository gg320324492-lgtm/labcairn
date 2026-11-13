# LC-P2-26 — the real-provider smoke credential (owner-side)

**Status.** The optional real-provider smoke remains **NOT RUN** in the frozen
P1 baseline. The harness reports `NOT RUN` and exits 2 for that class; no
session has spent a provider request as part of this closeout. This document
records the owner-side setup, not a credential and not a run.

**Read 2026-11-14:** the smoke has run since this was written — three times on
2026-10-28 against `MiniMax-M3.1-Flash` over an Anthropic-protocol endpoint
(twice locally, once on GitHub; `docs/THREAT-MODEL.md` §6.7 and
`docs/RELEASE-NOTES.md` §2.7), and the scheduled
`provider-smoke.yml` job has run green on the default branch since 2026-11-11.
The frozen P1 baseline keeps `real_model_smoke = NOT RUN` as its dated value;
these runs do not rewrite it.

**Why the required checks stay green.** `provider-smoke.yml` is deliberately
not a required `pull_request` check: it spends the owner's money and its
secret is not available to every actor. It runs on a schedule and by manual
dispatch. A required check that waits on a missing secret would be permanently
red, and a job that skips silently would be a green row measuring nothing.

## 1. The four configuration values

| Kind | Name | Where the owner sets it |
|---|---|---|
| repository secret | `LABCAIRN_PROVIDER_SMOKE_KEY` | GitHub → Settings → Secrets and variables → Actions → Secrets |
| repository variable | `LABCAIRN_PROVIDER_SMOKE_MODEL` | GitHub → Settings → Secrets and variables → Actions → Variables |
| repository variable | `LABCAIRN_PROVIDER_SMOKE_PROTOCOL` | the same Variables page |
| repository variable | `LABCAIRN_PROVIDER_SMOKE_BASE_URL` | the same Variables page |

`tests/test_real_provider_smoke.py` reads exactly these four configuration
values, plus one optional runner-temp output path. A key without the declared
model, protocol and base URL is refused by the workflow's loud preflight
check rather than producing a paid probe against an endpoint nobody named.

## 2. What the owner must decide and do

1. Choose the provider, model, protocol and base URL for one paid probe.
2. Add the key as a repository **secret**; never put it in the working tree,
   an issue, a pull request body, a log, a session transcript or a test.
3. Add the other three values as repository **variables** so the run record
   names what it measured.
4. Dispatch `provider-smoke.yml` manually on the default branch, or wait for
   its daily schedule, and read the run's report rather than trusting the
   exit code alone.
5. If the run is green, take a new baseline over the same comparison basis
   before claiming that the fifth class moved; the frozen P1 baseline keeps
   `real_model_smoke` as `NOT RUN` until its own record is replaced.

## 3. What this document does not do

- It does not hold, request, print or validate any secret value.
- It does not make `provider-smoke.yml` a required check.
- It does not change branch protection, enable auto-merge, or start CI.
- It does not turn an offline `NOT RUN` into a measured capability result.
- It does not authorise a session to spend money on a provider request.

The owner keeps the credential and the decision to spend. The workflow's
own witnesses in `tests/test_release_workflow.py` watch that the job cannot
become a required check, refuses loudly without a credential, reads the
probe report and writes it outside the checkout.
