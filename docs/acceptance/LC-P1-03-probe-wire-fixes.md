# LC-P1-03 — the probe's wire forms: acceptance

**Work order:** LC-P1-03 (the provider layer) · **Found by:** the LC-P2-01
pilot's first live probe, 2026-10-31 · **Status:** four defects found, four
fixed, four witnessed, and the live endpoint's capabilities re-measured.

**What this is.** Four defects in the capability probe's path, all of which
made a working endpoint look incapable. They are recorded here as a set
because they were found together, by one measurement, and because each one is
the same shape of mistake: **the probe spoke a wire form that no real
endpoint speaks.**

**What this is not.** It is not a claim that the endpoint is good. The probe
judges the answer, not the name, and that is unchanged. It is not the pilot:
no material was ingested, no task was run, and no business request was sent.

---

## 1. The measurement that found them

On 2026-10-31 the first live probe ran against an operator-configured
OpenAI-compatible endpoint, with the operator's own credential, outside the
repository. The probe reported **all four capabilities unsupported**:

| Capability | What the probe said | What the endpoint had actually done |
|---|---|---|
| `tool_calls` | "tool call arguments did not validate against the probe schema" | emitted a well-formed tool call |
| `structured_output_native` | "probe raised RuntimeError" | answered with the requested object |
| `structured_output_prompted` | "probe raised KeyError" | answered with the requested object |
| `usage_reporting` | "no probe response carried a usage block with a non-null counter" | returned a complete usage block |

The endpoint was reachable, the model answered every question, and every
answer was correct. Four independent defects in LabCairn turned four
successes into four refusals.

**The failure direction was safe, and that is exactly why it survived.** Each
defect reported *less capability than the endpoint had*, never more. A probe
that under-reports is a probe that blocks a run it could have made; it never
lets a run happen that should not. Safe, useless, and invisible — because
nothing in the suite could express the wire forms the endpoint used.

## 2. The four defects, and what each one was

| # | The defect | Why the verdict was wrong | The fix |
|---|---|---|---|
| D1 | A tool call's `arguments` arrive as a JSON **string** — the OpenAI wire form pydantic-ai keeps — and the probe compared them to the schema undecoded | a perfectly valid call compared as a non-object | the probe decodes the protocol's own field before comparing it (`probe.py`) |
| D2 | The prompted-output template was the schema JSON itself, and pydantic-ai renders that template with `str.format` | every brace of the schema read as a format field; the request died with `KeyError` before it was sent | the probe ships a fixed literal template carrying a `{schema}` placeholder |
| D3 | Each probe ran in its own event loop, while the httpx client's transport pooled connections across them | the second request inherited a keep-alive connection from a closed loop and died with `RuntimeError: Event loop is closed` | one session is one runner call: every request of a session runs on one loop |
| D4 | The usage sniffer kept the provider's `usage` block verbatim, while LC-P1-01's parser reads LabCairn's `input_tokens`/`output_tokens` | an OpenAI-compatible body reports `prompt_tokens`/`completion_tokens`, so every counter came back `Unknown(PROVIDER_OMITTED)` | the capture renames the wire names into the parser's vocabulary, at the one place that speaks wire |

**D1 and D4 are the same mistake in two layers**: a field whose value was
correct and whose *name* differed from the one the reader expected. D2 and D3
are the same mistake in the request path: the probe assumed a shape the
framework and the transport did not have.

## 3. Why the suite was green

The fake endpoint's fixtures all spoke LabCairn's vocabulary: tool-call
arguments were always dictionaries, and every usage block said
`input_tokens`. **A fake that cannot express the wire forms the real endpoint
uses cannot catch a probe that assumes them.** The blind spot was in the test
equipment, not only in the code.

Both gaps are closed: the fake now scripts a tool call's arguments as a JSON
string, and the usage fixtures speak the OpenAI names.

## 4. The witnesses

| # | The claim | The test |
|---|---|---|
| W1 | A tool call's arguments are decoded when they arrive as a JSON string, and refused by name when they are not JSON | `test_a_string_shaped_tool_call_argument_is_decoded`, `test_an_unparseable_string_argument_is_refused` |
| W2 | The prompted template is a fixed literal carrying `{schema}`, not the schema itself | `test_the_prompted_template_is_a_literal_with_a_schema_placeholder` |
| W3 | One session is one runner call, so every request of a session runs on one loop | `test_one_session_is_one_runner_call` |
| W4 | A usage block in OpenAI's wire names is measured, not omitted | `test_usage_reporting_reads_the_openai_wire_names`, `test_the_sniffer_renames_the_openai_wire_names_at_the_capture_point` |
| W5 | A block already in the parser's vocabulary is identity, not renamed twice | `test_the_sniffer_leaves_labcairn_vocabulary_untouched` |

## 5. The mutations, and what each one proved

Each mutation was applied to the working tree, run, and reverted; the count
is what reddened.

| Where | The mutation | What reddened | What it proved |
|---|---|---|---|
| D1 | the string decode disabled | 2 (W1) | the decode is what made a wire-form call pass |
| D2 | the template back to the schema JSON | 1 (W2) | the placeholder is the property, not the wording |
| D3 | one runner call per probe again | 1 (W3) | the session's single loop is watched, not assumed |
| D4 | the capture stops renaming the wire names | 2 (W4), and W5 stayed green | the rename is what made the measurement possible, and W5 is not collateral damage |

## 6. What was measured, and on what tree

- The live probe, before the fixes: **4 of 4 unsupported**.
- The live probe, after the fixes: **4 of 4 ok** — `tool_calls`,
  `structured_output_native`, `structured_output_prompted` and
  `usage_reporting`. Same endpoint, same model, same credential, one hour
  apart; the only difference is the tree.
- The local suites: the probe, usage, adapter and redaction suites green;
  the whole suite green on the tree that carries these four fixes.

## 7. What this does not carry

- **It does not make the model good.** LC-P2-14's question is untouched: a
  probe that measures the endpoint's abilities says nothing about whether the
  endpoint is right.
- **It does not send a business request.** The probe asks four fixed
  questions with no material in them; the pilot's real request is a separate
  authorisation, and the grant's scope and ceiling are the owner's to set.
- **It does not certify another endpoint.** These four defects were found on
  one endpoint; another vendor's wire forms are another measurement.
