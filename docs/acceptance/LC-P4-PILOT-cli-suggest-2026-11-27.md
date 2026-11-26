# LC-P4-PILOT — the CLI's own model request

**Ticket:** LC-P4-PILOT (the CLI route to a model, for material that carries
no comments)
**Date:** 2026-11-27.
**Tree:** based on `main` @ `9d3d4a7` ("Merge the removal's naming event into
main"), worktree `youthful-villani-266836`, Windows 11 Pro (10.0.26300 x64),
Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Command:** `labcairn --workspace <ws> suggest --source <source id>
--question "<text>" [--approval <id>] [--json]`.

**What is claimed here.** The product's only CLI route to a model was
`labcairn roles run`, and it refuses a chain that holds no comment — *a
judgement about a comment that is not there is invented*. That refusal is
the product's own and it is right there, but it meant that **material
carrying no comments could not be put to a model from the command line at
all**, and the pilot's first round
([`LC-P4-PILOT-first-round-2026-11-26.md`](LC-P4-PILOT-first-round-2026-11-26.md)
§3) had to go through the Python surface to make its one real request.

**This record says what the new command does, what was measured about it,
and what was not exercised.** The command is `suggest`: it reads the
material of one source, asks one question about it, sends **exactly one**
model request through the product's own consent gate, and writes the outcome
into the workspace.

**What is not claimed.** That the command made a real model request — **it
did not**. The witnesses use the project's own fakes: a stubbed transport at
the seam the wiring reads, and a synthetic credential in the environment. A
real request needs a key and a paid call, and this window was told not to
make one. What is witnessed is the command's use of the gate: how many
requests it makes, in what order, and what it writes.

---

## 1. The command, and the two steps it takes

`labcairn roles run` asks and then spends, and so does `suggest`.

**The ask** — a call with no `--approval`:

```
labcairn --workspace <ws> suggest --source src-... --question "..." --json
```

It reads the material, writes the question down, mints a **pending**
approval and prints its id. **Nothing is spent**: no request is sent, no
exchange is recorded, no money changes hands. The consent is a person's,
and it is given by `labcairn task approval-grant <id>`.

**The run** — a call with `--approval`:

```
labcairn --workspace <ws> suggest --source src-... --question "..." \
    --approval <id> --json
```

It spends that approval and sends **exactly one** request. The answer is
written into the task's own output area, and the machine-readable form
names the file and its digest.

**It is not the advisor loop, and it does not pretend to be.** `suggest`
asks a question; it judges no comment. What comes back is a model's answer
written into the workspace, and it is nobody's evidence.

---

## 2. What the tool read, and what it wrote

| Thing | Where it came from |
|---|---|
| the source's row | `labcairn.application.inspect_source` — the ledger's own record of the material: its kind, its hash, its size, its readability |
| the material's text | `labcairn.application.list_source_addresses` — the text the **ingestion** extracted, one address at a time, in the ledger's order. Not the file re-read |
| the provider, the model, the destination, the subject | the workspace's `providers.json`, under `model_suggestions` — the owner's own authorisation record |
| the transmit grant | `labcairn.application.approvals.register_access_grant` — the record turned into a row, so the gate checks it by the machinery every other transmit use is checked by |
| the consent | `labcairn.application.approvals.request_approval` / `grant_approval`, and `consent.consume` at the spend |
| the request | `labcairn.application.model_request.request_model` — **unchanged** |
| the two gates and their order | `labcairn.application.model_transmit.transmit_request` — **unchanged** |
| the answer's file | `labcairn.workspace.outputs.TaskOutputArea.write` — the task's own output area |

**No gate was rebuilt and no second one was invented.** The transmit check
runs first and only a permitted request consumes the approval; that order
is the layer's, and the command spends nothing of its own ahead of it.

**The question's digest goes into the approval's dependency list**, so the
approval binds the *question* and not only the material: an approval
granted for this question does not authorise another one, and the spend is
refused because the approval does not cover this question.

---

## 3. Where each number came from

| Number | What it is | Where it was measured |
|---|---|---|
| 13 | the witnesses in `tests/test_cli_suggest.py` | the file itself; `pytest --collect-only` on this tree |
| 114.8 s | the wall clock of one whole run of those 13 witnesses | `pytest tests/test_cli_suggest.py -q` on this machine — a **development** machine, not a runner |
| 36 | the tests in the three adjacent CLI suites, and 188.6 s for them | `pytest tests/test_cli_refusal_enumeration.py tests/test_cli_layer_models.py tests/test_cli_parameters.py -q` on this machine |
| 152 | the tests in the ten CLI files run together — this file's 13 among them — and 573.2 s for the run | `pytest` over the ten files on this machine |
| 31 | the tests in `tests/test_readme_accuracy.py`, run on their own | `pytest tests/test_readme_accuracy.py -q` on this machine |
| 12 | the mutations each witness was checked against | the mutation script; each mutation applied, the witness watched to go red, the file restored, the witness watched to go green again |
| 0 | real model requests | the transport was stubbed at the seam for every witness; no credential was read from `E:/labcairn-local/secrets/` and no paid call was made |

**Two of the 152 failed in the ten-file run, and neither is about this
work.** `tests/test_readme_accuracy.py::test_readme_commands_run` and
`::test_the_readme_documents_only_commands_that_exist` run `uv run
labcairn --help`, and `uv` could not fetch `hatchling` from PyPI — the
machine was offline at that moment. The file was run again on its own
afterwards and **31 passed**. The two failures are an environment, not a
regression; nothing in this work touches the README or the package build.

**The timings are a development machine's.** The shard costs are measured
on a runner, and the file this record's own test file belongs to is in no
shard — see §6.

---

## 4. The witnesses, and what would turn each one red

| Witness | Property it holds | Red when |
|---|---|---|
| `test_the_ask_writes_the_question_down_and_spends_nothing` | the ask spends nothing | a request was sent, or the approval was not pending |
| `test_the_ask_names_the_material_it_would_send` | the ask says what would leave | no material named, or the truncation not stated |
| `test_the_run_sends_exactly_one_request` | exactly one request | the transport was asked twice, or not at all |
| `test_the_request_carries_the_material_and_the_question` | what left is the question and the material | the prompt carried neither |
| `test_a_refused_transmit_leaves_the_approval_unspent` | **the transmit check runs before the approval is spent** | the approval was consumed, or a request went out |
| `test_the_approval_is_spent_only_by_a_request_that_went_out` | the consent bought a request | spent with no request, or unspent with one |
| `test_no_key_is_ever_printed_or_written` | no key printed or written | the key in the output, in the file, or in the database |
| `test_an_empty_question_is_refused_by_the_cli` | the CLI's own vocabulary | the empty question accepted, or the reason renamed |
| `test_a_workspace_that_names_no_provider_is_refused` | no provider, no request | a provider or a destination invented |
| `test_a_source_the_ledger_does_not_hold_is_refused` | the layer's vocabulary | the layer's reason renamed |
| `test_an_approval_that_covers_another_question_is_refused` | the consent binds the question | an approval for one question spent on another |
| `test_the_answer_is_written_into_the_workspace` | the answer is on disk | the file absent, or not carrying the answer |
| `test_a_source_with_no_comments_is_not_refused` | **not the advisor loop** | the advisor's refusal raised |

### 4.1 The mutations, one at a time

Each mutation breaks one property and leaves the rest of the tree alone.
For each: the mutation was applied, the witness was watched to go **red**,
the file was restored, and the witness was watched to go **green** again.

| # | The mutation | The witness it must turn red |
|---|---|---|
| M1 | the ask grants the approval it just minted | the ask spends nothing |
| M2 | the provider invocation asks twice | exactly one request |
| M3 | the approval is consumed **before** the transmit gate runs | the refused transmit leaves the approval unspent |
| M4 | the credential's value is written into the answer | no key printed or written |
| M5 | the empty question is accepted | the empty question is refused |
| M6 | the no-provider refusal is gone | no provider, no request |
| M7 | the layer's refusal is renamed into the CLI's | the layer's vocabulary |
| M8 | the approval binds the material but not the question | the consent binds the question |
| M9 | the file the answer is written to carries the question, not the answer | the answer is on disk |
| M10 | the command refuses material whose chain holds no comment | not the advisor loop |
| M11 | the excerpt is empty | the ask names the material |
| M12 | the prompt carries no material | what left is the question and the material |

**M3 is the one that matters most.** It is the ordering the whole command
exists to keep: a refusal has to cost the person nothing.

**A red that is red for the wrong reason is not a red.** One of the
mutations was written first as an edit that left the file syntactically
broken, and the witness duly failed — on a collection error, not on the
property. It was rewritten as an edit that leaves valid code and breaks
only the property, and that is the row above. A witness that fails for an
unrelated reason witnesses nothing.

---

## 5. The refusals, and whose vocabulary they are

The command's own, from `labcairn/cli/models.py`:

* `invalid_arguments` — *the question is empty*.
* `no_provider` — *the workspace names no provider to ask*, with the reason
  in the message: no `providers.json`, no authorisation record in it, an
  unreadable file, a provider the file does not configure, a provider with
  no credential, a transport that could not be wired.

Everything else is the layer's own vocabulary, and the witnesses check the
names rather than the prose: `source_not_found`,
`consent_scope_not_covered`, `approval_refused`.

**The enumeration found them.** `tests/test_cli_refusal_enumeration.py`
parses the CLI's package and requires every refusal it finds to have a
witness of its own; the two refusals above are watched by two of the
witnesses in this record, and the enumeration passed on this tree.

---

## 6. What the work did not exercise, and what the main session has to do

**Not exercised.**

* **No real model request.** The witnesses use the project's own fakes. A
  real request needs a key and a paid call.
* **No real provider transport.** The seam was stubbed; the provider
  layer's own gates were not crossed.
* **The pilot's copy was not asked about.** The command was exercised on a
  workspace of this window's own making. The pilot's copy is a `.docx`,
  and the command reads the text the ingestion extracted — which is the
  pilot's own path, but it was not run against the pilot's material here.
* **The API and the workbench do not have this command.** The command is
  the CLI's; the layer has no operation for it.

**For the main session.**

* **The shard list.** `tests/test_cli_suggest.py` is a new test file and
  **is in no shard**. `.github/ci-shards.json` needs it, and the cost has
  to be **measured on a runner**: `python .github/make_ci_shards.py` refuses
  to guess a cost it has not measured, and `python .github/remeasure_shards.py
  <run-id>` reads the per-file seconds out of a CI log. The mark, for the
  partition: this file is **13 e2e witnesses that run the CLI**, and it
  took **114.8 s** on a development machine — the order of magnitude only;
  the runner's number is the one that counts.
* **The layer operation.** The command assembles the request in the CLI
  package, because the layer has no operation for this shape and the
  `application` package was not this window's to change. `labcairn.cli`'s
  docstring says so in the same sentence that names the command. A layer
  operation would let the API and the workbench reach the same thing, and
  is worth doing when the shape is settled.

---

## 7. Where the material and the evidence live

* **The command:** `src/labcairn/cli/commands.py` (`suggest`, and the
  helpers `_the_suggestion`, `_the_ask`, `_the_answer`, `_the_excerpt`,
  `_the_prompt`, `_the_question_digest`, `_the_suggestion_wiring`,
  `_the_provider_wiring`), `src/labcairn/cli/models.py` (the two result
  models and the one new refusal reason), `src/labcairn/cli/render.py` (the
  two renderings), `src/labcairn/cli/__init__.py` (the package docstring,
  which names the command).
* **The witnesses:** `tests/test_cli_suggest.py`.
* **The run:** `pytest tests/test_cli_suggest.py -q`, with the tree's own
  `src` on `PYTHONPATH` and a `--basetemp` outside the repository.

**No real material is in this repository.** The document above carries ids,
digests, counts and paths, and no text of any material: the witnesses'
material is a sentence written by this window, and the pilot's copy never
entered the tree.
