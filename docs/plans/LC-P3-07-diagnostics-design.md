# LC-P3-07 — local de-identified diagnostics package (design)

> **DESIGN — not a deliverable until run on the installed build.**
> `LC-P3-07` stays `BLOCKED` on `LC-P3-05`'s installed build (work orders
> §12 decision 2, 2026-11-10): this is the substitute-first design of the
> diagnostics packaging surface §12 §5.6 deliverable 2 names, and its witness
> design. Nothing here was run; the package format is a design to be built
> against the installed build's actual behaviour, and every statement about
> what the *product* already does is anchored to the module and record named
> beside it.

Companion designs: [drill matrix](LC-P3-07-drill-matrix-design.md),
[backup/rollback](LC-P3-07-backup-rollback-design.md),
[manual skeleton](LC-P3-07-manual-skeleton.md). Work order:
[PHASE_3-work-orders.md](PHASE_3-work-orders.md) §12.

## 1. The claim being packaged

Execution plan §4's "Distribution and review" row (quoted in §12 §5.7) wants
diagnostics that a trial participant can hand to a supporter **without handing
over the material**. §12 §5.4 names the area: *"the diagnostics packaging
surface and its de-identification witness: local, de-identified diagnostics:
what is collected, what is proven absent."*

The architecture already states the invariant this package inherits —
[../ARCHITECTURE.md](../ARCHITECTURE.md), observability bullet: *"no telemetry
may carry source excerpts, credentials or user content"* — and the provider
layer already enforces its own half of it: `labcairn.providers.errors`'s
docstring rule 1–2 (*`ProviderFailure.detail_digest` is a function of the
scrubbed text*; *`ProviderFailure.message` is written here, by LabCairn, from a
fixed per-kind template — no third-party substring reaches it*) and
`ProviderFailure`'s own docstring (*"There is no `detail` field and there will
not be one"*). The diagnostics package is the same design applied to the whole
product surface rather than to one failed call: **the package carries digests
and counts, and the shapes of what may be absent are decided before anything
is collected.**

## 2. The package: an allowlist, not a dump

The package format is a fixed field allowlist. A field is in the package
because the allowlist names it and says why; a field not on the list is not
collected, not "collected then filtered". This is the same move `ProviderFailure`
made — a field that *could* hold a provider's error text is a field a future
caller will fill from `str(exc)` — applied at package scale.

### 2.1 The allowlist (design v1)

Every field below is derived from a module that already exists; the rightmost
column names where its value actually comes from today.

| # | Field | Why it is diagnosable | Where the value exists today |
|---|---|---|---|
| 1 | build identity: version, schema/migration head, platform | "which build failed" is the first question a supporter asks | the CLI's own report surfaces (`labcairn doctor` — `_doctor_report` in `src/labcairn/cli/commands.py`; its docstring: *"The findings are data and the prose is drawn from them, so the two cannot disagree"*) |
| 2 | task identity: `task_id` only | ties the package to one task's ledger without naming the task's content | `labcairn.core.ids.TaskId`; ledger rows key on it |
| 3 | operation states and transitions: `operation_id`, capability, state (`ATTEMPTING`/`UNCERTAIN`/…), event names | recovery questions are answered by state, and `describe_abandoned` already names operations this way | `src/labcairn/application/recovery.py`, `src/labcairn/recovery/contracts.py` |
| 4 | provider failures: `kind`, `retryable`, `user_action`, `detail_digest`, `message` | the whole provider-failure story, already LabCairn-authored by construction | `ProviderFailure.to_wire` in `src/labcairn/providers/errors.py` — the package embeds its exact output, nothing added |
| 5 | bounded-run counts: requests, refusals, failures, token totals, stop-loss verdict | the model half of a fault report needs counts, and `RunRecord` is *"digests and counts, never text"* | `RunRecord` / `RunRecord.to_counts` in `src/labcairn/providers/bounded_run.py` |
| 6 | capability probe verdicts (declared/verified/unsupported) | "the endpoint does not speak tool calls" is a diagnosis that names no content | `labcairn.providers.probe`, `ProviderCapabilities` in `labcairn.providers.capabilities` |
| 7 | credential **fingerprints** only | "the same credential twice" is diagnosable without the credential | `Credential`'s salted fingerprint in `labcairn.providers.credentials` (its docstring: *"identifies 'the same credential' for diagnostics without being a hash an attacker could grind"*) |
| 8 | refusal names + remedy text where the design states one | a refusal the operator can act on | `refusal.py`'s enum values; the precedent sentence shape is `describe_abandoned` (*"a refusal whose remedy is not stated is a dead end rather than a decision"*) |
| 9 | file facts **inside the task output area**: relative keys, `content_sha256`, `size_bytes` | "the publication exists and is these bytes" is a diagnosis; the hash is the store's own evidence currency | `WriteReceipt` in `labcairn.workspace.outputs`, `ArtifactReceipt` rows in the ledger |
| 10 | time facts: UTC moments of the events already recorded | ordering without wall-clock invention | the ledger events themselves (ADR-0003 — [../adr/ADR-0003-event-and-permission-model.md](../adr/ADR-0003-event-and-permission-model.md)) |

### 2.2 The deny-side (what is proven absent)

The package is required to *prove absence*, not merely promise restraint. The
absences the witness will assert, each by shape rather than by content:

- **no source material, no excerpt, no rendered prompt** — anything with a
  `SourceId`, a `source_key`, or an excerpt digest's *referent*;
- **no credential value** — only fingerprints (row 7), never `Credential.reveal`
  output;
- **no provider's raw error text** — row 4 is `to_wire()`'s output and `str(exc)`
  is never consulted (errors.py's rule 3: retryability is decided per kind,
  *"nothing else is consulted"*);
- **no absolute filesystem path into a source root** — row 9 is relative to the
  task output area; a path outside it names a person's directory;
- **no long verbatim run and no long Han run** — the same shape checks the
  outbound half already runs (§3).

## 3. How the deidentify pipeline is wired in

`labcairn.providers.deidentify` is the landed machinery (work orders §11;
record [../acceptance/LC-P3-06-substitute-first-2026-11-10.md](../acceptance/LC-P3-06-substitute-first-2026-11-10.md)),
and the diagnostics package should **reuse its verification half, not write a
second redaction story**. The design decision follows from the module's own
division of labour — *"the caller replaces, this module verifies"*:

1. **Verification before minting, again.** `DeidentifiedCase` is the only shape
   a bounded run accepts because nothing that failed verification can build it;
   the diagnostics package copies the type-level trick: a package is minted by
   a constructor that runs the checks, and there is no other constructor. A
   package that skipped verification has no representation — same argument as
   `redact_case`'s docstring (*"refuse, wholly"*).
2. **The shape checks, in the same order as `redact_case` runs them:**
   (a) **run-length** — `GRAM_WINDOW = 8`-word n-gram overlap between any
   package text and the task's material/excerpt digests' known renderings is
   refused (`DeidentificationRefusedError`), and no Han run of `HAN_RUN_CEILING
   = 8` or more survives (`_long_han_runs`);
   (b) **secret** — `_verify_no_named_secret` over every secret the caller
   registered;
   (c) **final scrub** — the pipeline's `Redactor` pass (`Redactor.scrub`,
   longest-first, `PLACEHOLDER` substitution; `contains_secret` is the
   post-scrub question).
   These catch the *content* leak the allowlist's *field* rule cannot: a
   diagnosis text that quotes the paper inside an allowed field.
3. **What the pipeline is *not* used for.** It never rewrites diagnosis text to
   make it safe (the same reasoning as deidentify's own: a rewriter has to
   decide what a name is — decisions about the material a pipeline cannot make).
   A field whose text fails verification is refused at mint time, and the
   package is not produced. The operator sees *"diagnostics refused"*, with the
   refusal naming the check — not a package whose fields were blanked out.
4. **The `SampleClass` question is deliberately absent.** The execution-plan
   split (synthetic vs. real material) classifies *cases that go outbound*; a
   local diagnostics package leaves the machine only when a person hands it
   over, and §12 §5.8 keeps real-material rows owner-gated. The package's class
   stamp is **[placeholder — decide at run against the installed build's real
   or synthetic usage; the trial's material is real].**

## 4. Refusing unlisted fields — and its witness

§12 §5.6 deliverable 2: *"with a witness asserting what is collected and what
is proven absent from the package."* The witness design has three rings, each
mutation-checked in the 03/06 manner (semantic mutation, product module, one
witness run, restored from `HEAD`):

| Ring | What it watches | The counter-mutation that must turn it red |
|---|---|---|
| **R1 — schema is the allowlist** | the package model accepts exactly the §2.1 fields and rejects a sixth (the landed precedent for this is the retrieval-metric sample table that *refuses a sixth field* — the same table-shape argument as `RunRecord`'s frozen count fields) | allow the package model an extra free-text field (or `extra="allow"`) and hand it a synthetic-material string → the refusal witnesses go red because a field that *can* carry content exists |
| **R2 — verification actually gates minting** | a package built from a rendering that fails a §3 check raises `DeidentificationRefusedError` and produces no package file | disable one verification rung in the minting path (the 06 record's mutation table did exactly this to `bound_excerpt_digest` and the whole-case precheck — R3/M5/Q3-rung rows) → the "refused, wholly" witness goes red |
| **R3 — the allowlist is what the witness measures** | the witness reads the produced package's own field names against the allowlist constant — asserting *the package says this*, not *we believe it* (the project's own rule: a check that reads its expected value from the thing it checks only agrees with itself; here the expected list is a constant in the test, and the observed list comes from the package) | reorder or widen the allowlist constant in the product module → the witness names which field moved in (and R1's refusal witness fails in the same run if the widened field is content-carrying) |

Anti-pattern the design refuses, recorded because the audit history named it: a
witness that asserts absence by *not looking* (a green run over a field it
never enumerated) is not a witness. Each absence in §2.2 is asserted by
enumerating the package's fields and checking each against its shape rule —
the way `tests/test_status_consistency.py::test_relative_links_in_docs_resolve`
enumerates links rather than spot-checking them.

**Registering the witness (when it lands, not now):** `pytestmark`, one entry in
`.github/ci-shards.json`, one gate-class row in `tests/evaluation/manifest.py` —
the three-place registration the 03/06 batches each performed; this design
batch adds none.

## 5. Where the package lives, and what "local" means

- The package is written **inside the task output area** — the one write door
  that already canonicalises, temp-files, `fsync`s and `os.replace`s
  (`TaskOutputArea.write`; §12 §5.3 keeps 07 from owning the installer, so the
  installed build's packaging is the installer's, not 07's).
- **[placeholder]** whether the installed build also offers a one-click export
  from the Electron shell (ADR-0023 keeps the served origin — the export
  button's path goes through the same API the CLI uses, but whether the shell
  offers it at all is the installed build's behaviour, not this design's).
- A package handed to a supporter is **a copy a person chose to share**;
  the product's obligation ends at "what the file contains is bounded". §12
  §5.3 keeps signing and distribution (`W28`) out of 07.

## 6. Open placeholders for the run

- **[placeholder]** the installed build's actual log surfaces (whether the
  structured-logging/OpenTelemetry-compatible interface ARCHITECTURE.md names
  exists in the build by trial time, and whether its records are a package
  *source* or stay out of scope);
- **[placeholder]** the `SampleClass` stamp decision (§3.4);
- **[placeholder]** package size caps measured on real trial failures
  (a count-only package should be small; "should" is not a measurement —
  the drill record measures it);
- **[placeholder]** whether `labcairn doctor --json` output is *the* diagnostics
  surface or one input to it (`_doctor_report`'s findings are already data —
  whether 07 wraps them or extends them is the installed build's decision).
