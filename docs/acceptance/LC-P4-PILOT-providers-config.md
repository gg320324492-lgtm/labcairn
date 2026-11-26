# LC-P4-PILOT — the machine-format provider configuration

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Status:** `MEASURED — the format is written down from the code that reads it, and the example below is the file one real request went through on 2026-11-25.`
**Measured:** 2026-11-25, on the tree at
`ea2a7711bd4523b5f53930a6bbf75e6f4ca77d81` (worktree `angry-poincare-b31569`),
Windows 11 Pro (10.0.26300 x64), Python 3.12.10.
**Related:** the owner's signed record,
[`LC-P4-PILOT-model-authorisation-draft.md`](../plans/LC-P4-PILOT-model-authorisation-draft.md);
the run that went through the example,
[`LC-P4-PILOT-real-request-2026-11-25.md`](LC-P4-PILOT-real-request-2026-11-25.md);
the wire boundary this file sits on,
[`LC-P4-G0-baseline-freeze.md`](../plans/LC-P4-G0-baseline-freeze.md) §5.

**Line numbers.** The `file:line` pointers name the lines as they stood at the
commit above; the tree has moved since. Follow the sentence, not the number.

## 1. Why this document is here, and why it is a document

**The authorisation record is prose; the machine reads a file.** The owner
signed a record whose fields are sentences — a provider, a model, an
endpoint, a purpose, a material boundary, a budget, a timeout, a retry
policy, a substitute, a set of stop conditions. The provider layer reads
none of that: it reads a JSON file in the workspace root, and it reads it
**strictly**. Until 2026-11-25 the file's shape existed in the code and in
no document in this tree, so the record could not be acted on by anyone who
had not read
`src/labcairn/providers/credentials.py` and
`src/labcairn/cli/commands.py` line by line. This document is that shape,
written down, with every field filled and every claim traced to the code
that reads it.

**Why not a shipped template.** The tree deliberately ships **no**
provider configuration:
`tests/test_provider_credentials.py::test_the_tree_ships_no_provider_configuration`
fails if a file named `providers.json` exists, if a `configs/` directory
exists, or if any `.json` file in the tree carries a top-level `providers`
object. ADR-0018 §D5 draws the line at *what the product reads*: **a route
is the operator's**. A tree that carried a filled provider configuration
would carry a route to a supplier, and a fresh checkout could then be
pointed at a paid endpoint by editing one file. So the example lives here,
in prose, where it is inert — and it names no credential, only the *place*
one is kept.

**Why `labcairn init` does not write it either.** `init` writes the root,
`materials/`, `output/`, the database, the policy and the workspace config
(`src/labcairn/cli/commands.py:436-464`). It writes no provider
configuration, and it is right not to: a file that names an endpoint is a
decision about a supplier, and `init` is not the place the owner makes it.

## 2. The file: name, place, and who writes it

| Question | Answer | Where it is decided |
|---|---|---|
| What is it called? | `providers.json` | `PROVIDERS_FILE_NAME`, `src/labcairn/cli/commands.py:106-110` |
| Where does it live? | In the **workspace root** — the same root every other command is bound to | `src/labcairn/cli/commands.py:2384` |
| Who writes it? | The operator. Nothing in the product writes it | `init` writes no such file (`commands.py:436-464`); the tree ships none |
| Who reads it? | The provider layer (`load_providers_config`) and the CLI's suggestion wiring (`_model_suggestions_record`) | `src/labcairn/providers/credentials.py:275-291`; `src/labcairn/cli/commands.py:2415-2461` |
| What if it is absent? | No provider, so the real-model suggestion backend is `None` and the service refuses with `model_suggestion_no_provider`. **Absence is the ordinary state**, not a fault | `commands.py:2354-2380`, `2384-2386` |

**The format is JSON, and the reason is historical rather than aesthetic**
(`credentials.py:278-280`): `tomllib` arrived in 3.11 and this is a 3.12
project, so JSON was the format available at the time; if the settings layer
grows, TOML belongs there and `load_providers_config` is where that changes.

## 3. The shape

Two top-level keys, and the roles they play are different.

```json
{
  "providers": { "<provider name>": { "<entry>": "<value>" } },
  "model_suggestions": { "<authorisation field>": "<value>" }
}
```

- **`providers`** — the **routes**: which endpoint, which model, which
  protocol, where the credential is, how long to wait. Required: a file
  without it is refused (`credentials.py:288-289`).
- **`model_suggestions`** — the **authorisation**: the owner's record, in
  the machine's own field names. Optional for the provider layer (which
  never reads it) and **required for the real-model suggestion path**,
  which reads it from the same file (`commands.py:2395-2397`).

**One thing the top level does not do: it does not refuse an unknown key.**
`load_providers_config` reads `raw["providers"]` and ignores the rest of the
document (`credentials.py:288-291`), and the authorisation reader reads
`raw["model_suggestions"]` and ignores the rest of the document
(`commands.py:2432-2435`). So a misspelled **top-level** key is silent: a
file with `provider` instead of `providers` is refused (the required key is
missing), while a file with `providers` *and* `model_suggestions` *and* a
stray `model_suggestion` key is accepted, and the stray key is read by
nobody. The **closed** sets are one level down, and they are closed on
purpose (§4 and §5).

## 4. The provider entry: six keys, closed

Every entry's key set is closed at six keys, and **an entry carrying a
seventh is refused rather than ignored** (`credentials.py:211-221`). The reason is
spelled out in the code: *"a config key LabCairn does not understand is far
more often a typo (`base_ur1`) than a forward-compatible extension, and a
typo that silently leaves `base_url` unset against an OpenAI-compatible
entry is a request going to the wrong place."*

| Key | Required? | Meaning | Read at |
|---|---|---|---|
| `protocol` | **yes** | The wire dialect: `openai`, `anthropic`, or `openai_compatible` | `credentials.py:222-228` |
| `model` | **yes** (non-empty) | The model identifier the provider is asked for | `credentials.py:165-167` |
| `base_url` | for `openai_compatible` | The API base; the protocol's own default applies when it is empty | `credentials.py:170-174`, `176-178` |
| `credential_env` | one of the two | The **name** of an environment variable holding the key — never the value | `credentials.py:257-258` |
| `credential_file` | one of the two | A file holding the key; surrounding whitespace is stripped | `credentials.py:260-267` |
| `timeout_s` | no (default `60.0`) | The per-request timeout handed to the HTTP client; must be positive | `credentials.py:162-163`, `165-169` |

**The credential is never in this file.** The file names *where the key
lives* — a variable name, or a path — and the value is read from there at
run time. The environment variable wins over the file when both are
configured (`credentials.py:255-258`), and a missing source is an error
that says where it looked and never what it found (`credentials.py:264-272`).

**An `openai_compatible` entry must name its own `base_url`** — there is no
default for a host the project does not know (`credentials.py:170-174`,
and `DEFAULT_BASE_URLS` at `credentials.py:73-78` lists only the two
protocols that have a documented public endpoint).

**The default anthropic base URL carries a `/v1` the client would duplicate.**
`DEFAULT_BASE_URLS[ANTHROPIC]` is `https://api.anthropic.com/v1`
(`credentials.py:75-78`), and the client appends `/v1/messages` to whatever
base URL it is given (§8). Measured on 2026-11-25: that default composes to
`https://api.anthropic.com/v1/v1/messages`, while
`https://api.anthropic.com` composes to
`https://api.anthropic.com/v1/messages`. **So an `anthropic` entry must name
its `base_url` explicitly, and that base URL must not end in `/v1`.** The
authorised MiniMax entry does both.

## 5. The authorisation record: eight fields, closed

`model_suggestions` is the owner's record in the machine's field names. Its
field set is **closed** (`commands.py:133-144`): a record carrying an
unknown field authorises **nothing** (`commands.py:2436-2438`), on the same
standard the provider entry applies.

| Field | Required? | Meaning | Read at |
|---|---|---|---|
| `provider` | **yes** | The key of the provider entry to use | `commands.py:149-155`, `2399-2400` |
| `destination` | **yes** | Where material may be sent — the destination the transmit grant names | `commands.py:2504-2542` |
| `subject_ref` | **yes** | The subject the grant is about — the material the grant covers | `commands.py:2528-2531` |
| `granted_by` | **yes** | Who granted it | `commands.py:2535` |
| `granted_at` | **yes** | When, as an ISO timestamp | `commands.py:2518-2521`, `2452-2454` |
| `expires_at` | no | When it lapses, as an ISO timestamp | `commands.py:2522-2526` |
| `scope` | no (defaults to `<subject_ref>/**`) | The narrowed scope | `commands.py:2532-2533` |
| `grant_id` | no (defaults to `grant-model-suggestions-<subject_ref>`) | The grant's identity | `commands.py:2529` |

**A required field left empty or filled with the placeholder refuses the
record.** `TBD by owner` is the marker, and a record carrying it authorises
nothing (`commands.py:123-127`, `2446-2449`). An optional field that is
absent is narrowed to the default the table names; an optional field that is
present must still hold a real value.

**A record that passes is turned into a row, not a decision.**
`_suggestion_grant` builds the :class:`Grant` the permission layer checks
(`commands.py:2504-2542`) and `register_access_grant` writes it
(`src/labcairn/application/approvals.py:487-527`), so the operator's
authorisation is checked by the same machinery every other transmit use is
checked by — the suggestion loop gets no parallel permission path.

**What the record does not carry.** The credential (it is in the provider
entry's `credential_env` / `credential_file`), the budget, the retry policy,
the substitute and the stop conditions. Those live in the product's own
machinery — the budget in the adapter, the retry classification in the
suggestion loop — and the signed authorisation record states them for the
run, not for the file.

## 6. The complete example

Every field filled, with the values the signed authorisation record names.
**This is the file one real request went through on 2026-11-25**
(`LC-P4-PILOT-real-request-2026-11-25.md`); its digest is recorded there.
**One field was added to it on 2026-11-26:** that run had nowhere to put an
output ceiling, so the ceiling was added where the transport was assembled and
the digest recorded there is of the file without it.

```json
{
  "providers": {
    "minimax": {
      "protocol": "anthropic",
      "model": "MiniMax-M3.1-Flash",
      "base_url": "https://api.minimax.cn/anthropic",
      "credential_file": "E:/labcairn-local/secrets/minimax-m31-flash-active.txt",
      "timeout_s": 60,
      "max_output_tokens": 6089
    }
  },
  "model_suggestions": {
    "provider": "minimax",
    "destination": "https://api.minimax.cn/anthropic",
    "subject_ref": "pilot/LC-P4-PILOT/desensitised-copy",
    "granted_by": "owner",
    "granted_at": "2026-11-24T00:00:00+00:00",
    "expires_at": "2026-12-24T00:00:00+00:00",
    "scope": "pilot/LC-P4-PILOT/desensitised-copy/**",
    "grant_id": "grant-model-suggestions-pilot/LC-P4-PILOT"
  }
}
```

**Every value, and where it comes from.**

| Value | Source |
|---|---|
| `protocol`, `model`, `base_url` | The signed record §1: MiniMax, `MiniMax-M3.1-Flash`, `https://api.minimax.cn/anthropic`, protocol `anthropic` |
| `credential_file` | The operator's single-line key file, outside the repository. The LC-P2-18 run wrote this one after probing it `ok`. **Corrected 2026-11-25, by measurement:** the older `minimax-key.txt` that LC-P2-18 calls *retired* holds **the same key** — the providers layer's credential fingerprint is identical for the two — so what was retired is a file name, not a secret. The three-line file `minimax-m31-flash.txt` is the different key, and the one LC-P2-18 did not probe. The file named above is the right one to name, and the reason is not that the other is broken but that this one is the current one |
| `timeout_s` | The signed record §5: 60 seconds |
| `max_output_tokens` | The provider's own reported output tokens for the pilot's round A — **6,089** (`LC-P4-PILOT-real-request-2026-11-25.md` §8.4) — which is the ceiling that run was completed under, added here on 2026-11-26 because the file had nowhere to put one. **A ceiling, not a constant:** three readings of that one prompt ranged over 2,231 → 6,089, so the figure is the largest of them and a ceiling written from a single reading is a bet. Optional; an entry that does not name it runs under the provider's own default |
| `provider` | The key of the provider entry above |
| `destination` | The endpoint the grant permits transmitting to |
| `subject_ref`, `scope` | The material the grant covers: the desensitised pilot copy. **This is the field the pilot's own copy must fill once the desensitisation checklist is signed** — see §7 |
| `granted_by`, `granted_at`, `expires_at` | The signed record: `owner`, 2026-11-24, and the 2026-12-24 expiry |
| `grant_id` | The record's own identity; the default would have been `grant-model-suggestions-pilot/LC-P4-PILOT/desensitised-copy` |

**A note on the credential path.** It is a path on the operator's machine,
and the file it names holds a secret. The repository records *where* a
credential is kept and never *what* it is; the key's value appears nowhere
in this tree, in the run's artefacts, or in any log. The LC-P3-06 precedent
recorded the same fact the same way — *"a single-line key outside the
repository"* — and this document names the file because the workspace that
already exists points at the **older** one (§8), and a reader has to be
able to see which copy a request will actually read.

## 7. What the example cannot fill yet

**The `subject_ref` above is a shape, not a signed pointer.** The signed
record's §2 permits *"the desensitised copy registered by the
desensitisation checklist and its excerpts only"*, and the checklist
([`LC-P4-PILOT-desensitisation-checklist.md`](../plans/LC-P4-PILOT-desensitisation-checklist.md))
is still `DRAFT` — its part-D result, the one that registers the copy's
digest and metadata, is unsigned. So **no registered excerpt exists to
send**, and the field that names the material cannot be filled with a
registered pointer until it is. The example carries a shape that is
obviously a placeholder for that pointer; a run against it sends no
registered material, and the run of 2026-11-25 sent none (§3 of the run
record).

## 8. How a bad file is refused, and what that leaves unguarded

The reader is strict, and each refusal names what is wrong:

| A file that… | Is refused by | With |
|---|---|---|
| has no top-level `providers` object | `load_providers_config` | `must have a top-level "providers" object` |
| is not valid JSON | `load_providers_config` | `is not valid JSON: <message>` |
| carries an unknown key in a provider entry | `ProviderSettings.from_mapping` | `unknown provider settings key(s): <names>` |
| names an unknown `protocol` | `ProviderSettings.from_mapping` | `protocol 'x' is not one of openai, anthropic, openai_compatible` |
| has an entry with an empty `model` | `ProviderSettings.__post_init__` | `provider settings need a model name` |
| has `timeout_s` ≤ 0 | `ProviderSettings.__post_init__` | `timeout_s must be positive` |
| is an `openai_compatible` entry with no `base_url` | `ProviderSettings.__post_init__` | `an OpenAI-compatible endpoint must name a base_url` |
| names a credential file that does not exist | `load_credential` | `credential file <path> does not exist` |
| has a `model_suggestions` record with an unknown field | `_model_suggestions_record` | silently: the record authorises nothing |
| has a record with an empty or `TBD by owner` field | `_model_suggestions_record` | silently: the record authorises nothing |
| has a record whose `granted_at` is not a timestamp | `_model_suggestions_record` | silently: the record authorises nothing |
| names a `provider` the file does not configure | `model_suggestion_backend` | silently: no backend |

**The last four are silent by design**, and the reason is in the code: *"the
record's own fill state is the operator's to check, and a service that
logged one line per missing field would turn every unauthorised start-up
into a warning about the one feature the record does not cover"*
(`commands.py:2415-2424`). The refusal the caller sees is
`model_suggestion_no_provider`, and the operator's next step is to read
this document.

**One thing nothing in the file gates: the capability probe.** The
suggestion path builds its adapter with **no** `required_capabilities`
(`commands.py:2623-2630`), and the adapter's capability gate returns
immediately when that set is `None` (`src/labcairn/providers/adapter.py:476-478`).
The G5 acceptance record measured this supplier's
`structured_output_native` and `structured_output_prompted` as
**unsupported**, and the probe record is not consulted on this path at all.
**That is correct for the path as built** — the suggestion path sends a
plain-text prompt and reads a plain-text answer
(`src/labcairn/application/model_suggestions.py:148-173`, `301-313`), so it
needs no structured output. **It also means nothing stops an unknown
endpoint before a request goes out**: a wrong `base_url` is discovered by
the request failing, not by the file being refused. The file's own
refusals are about *shape*; a route that answers is a route that spends.

## 9. The two questions this file does not answer

1. **Does `base_url` need a trailing path element?** No — and the client
   says so. The Anthropic client appends `/v1/messages` to the base URL it
   is given, so `https://api.minimax.cn/anthropic` is the whole route, and
   a base URL ending in `/v1` would be doubled. Measured on 2026-11-25
   against a local fake: the request line was `POST /anthropic/v1/messages?beta=true`.
   The run record carries the same measurement against the real endpoint.
2. **Is the capability probe a gate on the suggestion path?** No (§8). The
   path's own request shape does not need one, and the run of 2026-11-25
   went out with **no probe record at all** — which is the shape the
   LC-P3-06 precedent used, and the reason its capability record was named
   rather than re-measured.
