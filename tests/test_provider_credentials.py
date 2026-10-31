"""Credentials and provider configuration.

The repository forbids real credentials anywhere, including fixtures, so nothing
in this file reads the ambient environment. Every test passes an explicit
``environ`` mapping — which is also why
:func:`~labcairn.providers.credentials.load_credential` takes ``environ`` as a
parameter rather than reaching for :data:`os.environ`: a test that *could*
inherit a developer's real key is a test that eventually prints one.

The one place that does read the environment is the live probe, and it lives in
:mod:`tests.test_real_provider_smoke` rather than here, so "which file may spend
money" is answered by a filename rather than by searching for a marker. What is
witnessed here is the *predicate* that decides whether that file runs — it is
filed under the unit class, so every offline run checks the rule that keeps it
offline instead of trusting it.

The synthetic key used throughout is obviously not a real credential.

**The last section is about the *tree* rather than about the product.** The
sentence *"a fresh checkout cannot spend money by accident"* has two halves —
one about the product's behaviour and one about the bytes on disk — and only
the first was watched. A supplier's identity is the operator's configuration
and never the tree's, so what the tree holds is a question about files, and
these witnesses read files.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest
from test_real_provider_smoke import (
    SMOKE_BASE_URL_ENV,
    SMOKE_KEY_ENV,
    SMOKE_MODEL_ENV,
    SMOKE_PROTOCOL_ENV,
    SMOKE_RECORD_ENV,
    live_settings,
)

from labcairn.providers.credentials import (
    DEFAULT_BASE_URLS,
    Credential,
    MissingCredentialError,
    Protocol,
    ProviderSettings,
    UnknownProviderError,
    load_credential,
    load_providers_config,
)
from labcairn.providers.pydantic_models import auth_header_name

FAKE_KEY = "sk-ant-not-a-real-key-abcdef0123456789"


def _settings(**overrides: object) -> ProviderSettings:
    base: dict[str, object] = {
        "protocol": Protocol.OPENAI,
        "model": "claude-sonnet-5",
        "credential_env": "LABCAIRN_TEST_ONLY_KEY",
    }
    base.update(overrides)
    return ProviderSettings(**base)  # type: ignore[arg-type]


# --- sources ---------------------------------------------------------------


@pytest.mark.unit
def test_a_credential_is_read_from_the_named_environment_variable() -> None:
    credential = load_credential(_settings(), environ={"LABCAIRN_TEST_ONLY_KEY": FAKE_KEY})
    assert credential.reveal() == FAKE_KEY
    assert credential.source == "env:LABCAIRN_TEST_ONLY_KEY"


@pytest.mark.unit
def test_surrounding_whitespace_is_stripped_because_every_editor_adds_it() -> None:
    """A trailing newline in an ``Authorization`` header is a 401 that looks
    like a wrong key — the single most common self-inflicted config bug."""
    credential = load_credential(_settings(), environ={"LABCAIRN_TEST_ONLY_KEY": f"  {FAKE_KEY}\n"})
    assert credential.reveal() == FAKE_KEY


@pytest.mark.unit
def test_a_configured_file_is_the_second_source(tmp_path: Path) -> None:
    key_file = tmp_path / "provider.key"
    key_file.write_text(FAKE_KEY + "\n", encoding="utf-8")

    credential = load_credential(_settings(credential_file=key_file), environ={})
    assert credential.reveal() == FAKE_KEY
    assert credential.source.startswith("file:")


@pytest.mark.unit
def test_the_environment_wins_over_a_file(tmp_path: Path) -> None:
    key_file = tmp_path / "other.key"
    key_file.write_text("sk-ant-from-the-file-000000000", encoding="utf-8")

    credential = load_credential(
        _settings(credential_file=key_file), environ={"LABCAIRN_TEST_ONLY_KEY": FAKE_KEY}
    )
    assert credential.reveal() == FAKE_KEY


@pytest.mark.unit
def test_no_credential_anywhere_says_where_it_looked() -> None:
    """The error names the *variable*, never a value, and never invents a source."""
    with pytest.raises(MissingCredentialError) as raised:
        load_credential(_settings(), environ={})
    assert "LABCAIRN_TEST_ONLY_KEY" in str(raised.value)

    with pytest.raises(MissingCredentialError) as raised:
        load_credential(_settings(credential_env=None, credential_file=None), environ={})
    assert "none configured" in str(raised.value)


@pytest.mark.unit
def test_a_missing_credential_file_is_an_error_not_an_empty_credential() -> None:
    """Silently continuing with an empty key would produce a 401 that reads as
    "the provider is down"."""
    with pytest.raises(MissingCredentialError) as raised:
        load_credential(
            _settings(credential_env=None, credential_file=Path("does-not-exist.key")), environ={}
        )
    assert "does not exist" in str(raised.value)


@pytest.mark.unit
def test_an_empty_credential_is_refused() -> None:
    with pytest.raises(MissingCredentialError):
        Credential.of("   ", source="env:X")
    with pytest.raises(MissingCredentialError):
        load_credential(_settings(), environ={"LABCAIRN_TEST_ONLY_KEY": ""})


# --- the three protocols ---------------------------------------------------


@pytest.mark.unit
def test_the_three_required_protocols_are_configurable() -> None:
    """At least OpenAI, Anthropic, and one OpenAI-compatible custom endpoint."""
    openai = _settings(protocol=Protocol.OPENAI)
    anthropic = _settings(protocol=Protocol.ANTHROPIC)
    compatible = _settings(
        protocol=Protocol.OPENAI_COMPATIBLE,
        model="qwen2.5-7b-instruct",
        base_url="https://gateway.internal/v1",
    )

    assert openai.effective_base_url == DEFAULT_BASE_URLS[Protocol.OPENAI]
    assert anthropic.effective_base_url == DEFAULT_BASE_URLS[Protocol.ANTHROPIC]
    assert compatible.effective_base_url == "https://gateway.internal/v1"
    assert auth_header_name(Protocol.ANTHROPIC) == "x-api-key"
    assert auth_header_name(Protocol.OPENAI_COMPATIBLE) == "Authorization"


@pytest.mark.unit
def test_an_openai_compatible_endpoint_must_name_its_own_base_url() -> None:
    """There is no default for a host the project does not know.

    Silently falling back to ``api.openai.com`` would send a user's self-hosted
    gateway traffic to a third party — the exact disclosure failure the work
    order's acceptance line is about.
    """
    with pytest.raises(ValueError, match="must name a base_url"):
        _settings(protocol=Protocol.OPENAI_COMPATIBLE)
    # And with one, it is honoured verbatim.
    settings = _settings(protocol=Protocol.OPENAI_COMPATIBLE, base_url="http://localhost:8080/v1")
    assert settings.effective_base_url == "http://localhost:8080/v1"


@pytest.mark.unit
def test_a_base_url_that_carries_a_credential_is_sanitised_for_the_fingerprint() -> None:
    """``?api_key=`` on a self-hosted gateway is a common deployment, not an error."""
    settings = _settings(
        protocol=Protocol.OPENAI_COMPATIBLE,
        base_url="https://user:secret@gateway.internal/v1?api_key=sk-leaked-in-a-url",
    )
    sanitised = settings.sanitised_base_url()

    assert sanitised == "https://gateway.internal/v1"
    assert "secret" not in sanitised
    assert "sk-leaked" not in sanitised
    assert "@" not in sanitised


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides",
    [
        {"model": "  "},
        {"timeout_s": 0},
        {"timeout_s": -1},
    ],
)
def test_nonsensical_settings_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _settings(**overrides)


# --- the config file -------------------------------------------------------


@pytest.mark.unit
def test_a_providers_config_file_is_parsed_strictly(tmp_path: Path) -> None:
    config = tmp_path / "providers.json"
    config.write_text(
        json.dumps(
            {
                "providers": {
                    "local": {
                        "protocol": "openai_compatible",
                        "model": "qwen2.5-7b-instruct",
                        "base_url": "http://localhost:8080/v1",
                        "credential_env": "LOCAL_KEY",
                        "timeout_s": 30,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    providers = load_providers_config(config)
    local = providers["local"]
    assert local.protocol is Protocol.OPENAI_COMPATIBLE
    assert local.model == "qwen2.5-7b-instruct"
    assert local.timeout_s == 30.0


@pytest.mark.unit
def test_a_misspelled_config_key_is_an_error_rather_than_a_silent_default() -> None:
    """``base_ur1`` would otherwise leave ``base_url`` unset and send the
    request to the wrong place."""
    with pytest.raises(ValueError, match="unknown provider settings key"):
        ProviderSettings.from_mapping(
            {
                "protocol": "openai_compatible",
                "model": "m",
                "base_ur1": "http://localhost:8080/v1",
            }
        )


@pytest.mark.unit
def test_an_unrecognised_protocol_names_the_there_are_ones() -> None:
    with pytest.raises(UnknownProviderError) as raised:
        ProviderSettings.from_mapping({"protocol": "llama-cpp-server", "model": "m"})
    assert "openai" in str(raised.value)
    assert "anthropic" in str(raised.value)
    assert "openai_compatible" in str(raised.value)


@pytest.mark.unit
def test_a_malformed_config_file_is_reported_as_such(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(MissingCredentialError):
        load_providers_config(missing)

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_providers_config(broken)

    wrong_shape = tmp_path / "wrong.json"
    wrong_shape.write_text('{"models": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match='top-level "providers"'):
        load_providers_config(wrong_shape)


# --- the real-provider wiring -----------------------------------------------


@pytest.mark.unit
def test_the_usage_sniffer_is_the_clients_transport_not_a_side_channel() -> None:
    """The sniffer must be *in* the request path, or it observes nothing.

    Asserted structurally rather than by making a request: the point is the
    wiring, and a test that issued a live call to check it would be exactly the
    thing this work order may not do.
    """
    import httpx

    from labcairn.providers.pydantic_models import build_http_client, make_sniffer

    sniffer = make_sniffer()
    client = build_http_client(_settings(), sniffer=sniffer)

    assert client._transport is sniffer
    assert isinstance(client, httpx.AsyncClient)
    assert sniffer.inner is not None, "a sniffer with no inner transport forwards to nothing"
    asyncio.run(client.aclose())


@pytest.mark.unit
def test_a_client_without_a_sniffer_is_still_constructible_and_still_safe() -> None:
    """Omitting the sniffer must not crash — it must simply measure nothing."""
    from labcairn.providers.pydantic_models import build_http_client

    client = build_http_client(_settings())
    assert client._transport is not None
    asyncio.run(client.aclose())


# --- the live smoke's gate ---------------------------------------------------
#
# The probe itself is in tests/test_real_provider_smoke.py. What decides whether
# that file runs is tested here, in the unit class, because a rule that gates a
# class may not be checked only inside the class it gates: the offline run would
# then never test the rule that keeps it offline.


@pytest.mark.unit
def test_the_live_smoke_is_configured_only_by_the_named_variables() -> None:
    """Which variables may turn the live smoke on, and which may not.

    Three properties, each of which the version of the probe that lived inside
    this file got wrong in a different way:

    * the model, protocol and base URL come from the environment, so the run
      declares what it probed — the old test hard-coded them, and so could not
      have run against any endpoint the owner actually held;
    * a key **without** a model is a skip rather than a guess, because a probe
      against an endpoint's default model names no model;
    * a credential that merely happens to be in the machine's environment —
      ``ANTHROPIC_API_KEY``, say — does not enable it. LC-P1-03's rule was that
      the project must not spend a key it was never given, and that rule belongs
      in the code that decides whether to run, not in prose.
    """
    configured = live_settings(
        {
            SMOKE_KEY_ENV: FAKE_KEY,
            SMOKE_MODEL_ENV: "some-model-id",
            SMOKE_PROTOCOL_ENV: Protocol.ANTHROPIC.value,
            SMOKE_BASE_URL_ENV: "https://gateway.example/anthropic",
        }
    )
    assert configured is not None
    assert configured.model == "some-model-id"
    assert configured.protocol is Protocol.ANTHROPIC
    assert configured.effective_base_url == "https://gateway.example/anthropic", (
        "the gateway prefix is the whole configuration: the SDK appends its own "
        "path, and a run that dropped the base URL would probe Anthropic instead"
    )
    assert configured.credential_env == SMOKE_KEY_ENV, (
        "the settings must name the variable, so the secret is resolved by the "
        "credential loader and never carried in the settings object"
    )

    assert live_settings({SMOKE_KEY_ENV: FAKE_KEY}) is None, (
        "a key with no declared model must not run: the record would name no model"
    )
    assert live_settings({SMOKE_MODEL_ENV: "some-model-id"}) is None
    assert live_settings({"ANTHROPIC_API_KEY": FAKE_KEY, "ANTHROPIC_MODEL": "x"}) is None, (
        "a credential found in the machine's environment is not one the owner supplied"
    )


@pytest.mark.unit
def test_the_live_smoke_is_skipped_when_no_credential_was_supplied() -> None:
    """The CI path is a skip, not a failure and not a spend.

    This is the witness that keeps the ``requires_provider`` marker honest. CI
    runs test files by name with no marker filter, so the only thing between a
    green pipeline and a paid request is this predicate — and the record path is
    an output, so setting it alone must not enable a run.
    """
    assert live_settings({}) is None
    assert live_settings({SMOKE_KEY_ENV: "   ", SMOKE_MODEL_ENV: "m"}) is None, (
        "a whitespace-only variable is not a credential"
    )
    assert live_settings({SMOKE_RECORD_ENV: "out.json", SMOKE_MODEL_ENV: "m"}) is None


# --------------------------------------------------------------------------- #
# The tree's half: what a fresh checkout carries
# --------------------------------------------------------------------------- #
#
# Everything above is about the *product*: where a credential comes from, how a
# settings file is read, what a protocol is. What follows is about the **tree**
# — the bytes a reviewer downloads — because the sentence *"a fresh checkout
# cannot spend money by accident"* has two halves and only one of them was
# watched.
#
# **A route is the operator's.** ADR-0018 §D5: *"a model id is configuration,
# and a capability claim is a measurement."* The tree may hold the
# **vocabulary** — the protocol labels, the capability names, the two public
# endpoints the two protocols' own documentation names — and it may not hold a
# **route**: which supplier, which model, which endpoint, what it costs, what
# it can do. The line is drawn at *what the product reads*: a string in a
# docstring is prose, a string in a settings file is a route.
#
# Every fact below is read out of a file in the checkout. A value that happens
# to be importable, or a string that happens to be in the installed package,
# is a fact about the machine — and the mutations these witnesses are written
# for are the ones that change the **tree** and leave everything installed
# exactly as it was.

#: The configuration file the product reads a route from. One name, one
#: format: ``load_providers_config`` is the reader, and the CLI looks for
#: exactly this name in a **workspace** root.
PROVIDERS_FILE_NAME = "providers.json"

#: The keys the provider settings format has. **Closed**: an entry carrying
#: anything else is refused rather than ignored.
SETTINGS_KEYS: frozenset[str] = frozenset(
    {"protocol", "model", "base_url", "credential_env", "credential_file", "timeout_s"}
)

#: The two public endpoints the tree names, and the only two. ADR-0019 §D2
#: calls them *protocol defaults* — library knowledge of where the two
#: protocols' documented endpoints sit — and not this project's choice of a
#: supplier. The third protocol has no default at all: its host is the
#: operator's to name.
PROTOCOL_DEFAULT_BASE_URLS: frozenset[str] = frozenset(
    {"https://api.openai.com/v1", "https://api.anthropic.com/v1"}
)

#: Words that would make a settings key a price or a capability claim. A
#: capability claim is a *measurement* (ADR-0018 §D5) and a price belongs to a
#: table the project does not ship, so the format has no room for either.
PRICE_OR_CAPABILITY_WORDS: tuple[str, ...] = (
    "price",
    "cost",
    "usd",
    "capab",
    "supports",
    "billing",
)

#: A URL as it appears in a source file: a scheme, ``://``, and something after
#: it. ``://`` on its own — the separator a parser splits on — is not a URL.
URL_LITERAL: re.Pattern[str] = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://\S+$")


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Git, asked about the tree rather than about the filesystem.

    Git is the authority on what the tree *is*: ``.venv`` and
    ``node_modules`` are under the checkout and are not the tree, and a file
    that is about to be committed is in the tree in a way a walk of the
    filesystem cannot tell.
    """
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )


def _tree_paths(repo_root: Path) -> list[str]:
    """Every path the tree holds: the tracked ones, and the untracked not ignored.

    **Both.** A file that is about to be committed is held to the same rule as
    one that already is, and the untracked-but-not-ignored set is what a
    reviewer's ``git status`` shows.
    """
    proc = _git(repo_root, "ls-files", "--cached", "--others", "--exclude-standard")
    assert proc.returncode == 0, f"git ls-files failed: {proc.stderr}"
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert paths, "the tree listing is empty, so the sweep proved nothing"
    return paths


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """The ids of the string nodes that are docstrings.

    **A docstring is prose.** It is where the tree keeps the shape of a
    provider label and the name of a wire dialect; it is not a value the
    product reads. The witnesses below separate the two, because a string that
    only appears in prose cannot configure anything and a string that appears
    in code can.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _code_literals(path: Path) -> list[tuple[int, str]]:
    """Every string constant in a module that is not a docstring, with its line."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_nodes(tree)
    literals: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            literals.append((node.lineno, node.value))
    return literals


def _provider_layer_paths(repo_root: Path) -> list[Path]:
    """The modules that talk to a provider, and the seam they implement."""
    paths = sorted((repo_root / "src" / "labcairn" / "providers").rglob("*.py"))
    paths += sorted((repo_root / "src" / "labcairn" / "core" / "providers").rglob("*.py"))
    assert paths, "the provider layer was not found; the sweep proved nothing"
    return paths


def _accepted_settings_keys(repo_root: Path) -> set[str]:
    """The keys the settings format accepts, read out of the tree's own source.

    **Read out of the file in the checkout**, not out of the installed
    package: an installed package is a fact about the machine, and a value
    that can change is re-measured rather than carried forward.

    The reader **fails loudly when it cannot find the set** — a witness that
    cannot look must not pass. The *format* is what is closed, and the format
    is the set of keys the reader accepts, so the reader is the thing to read.
    """
    path = repo_root / "src" / "labcairn" / "providers" / "credentials.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "from_mapping":
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "known" for target in inner.targets
            ):
                continue
            if not isinstance(inner.value, ast.Set):
                continue
            return {
                element.value
                for element in inner.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    pytest.fail(
        f"{path} holds no 'known = {{...}}' set of accepted settings keys, so the "
        "schema this witness is about could not be read. If the format changed "
        "shape, this reader has to change with it — a witness that cannot look "
        "must not pass."
    )


@pytest.mark.unit
def test_the_tree_ships_no_provider_configuration(repo_root: Path) -> None:
    """A fresh checkout holds nothing that could name a supplier.

    **The route is the operator's file.** ``load_providers_config`` reads
    ``providers.json``, and the CLI looks for that name in a **workspace**
    root — not in the checkout and not in the package. So the tree's half of
    *"a fresh checkout cannot spend money by accident"* is that there is
    nothing in it for the product to read: no file with that name, no
    ``configs/`` directory, and no JSON file shaped like a provider
    configuration whatever it is called.

    **Every JSON file in the tree is read**, not the ones somebody thought of
    to check: a configuration under a name the product does not use would
    still be a route somebody wrote down, and the claim is about the tree
    rather than about one filename.
    """
    paths = _tree_paths(repo_root)

    named = sorted(path for path in paths if PurePosixPath(path).name == PROVIDERS_FILE_NAME)
    assert not named, (
        f"the tree holds {named}. The product reads exactly this name, so a file "
        "with it is a configuration somebody wrote down."
    )

    in_configs = sorted(path for path in paths if "configs" in PurePosixPath(path).parts)
    assert not in_configs, f"the tree holds a configs/ directory: {in_configs}"

    shaped: list[str] = []
    for path in paths:
        if not path.lower().endswith(".json"):
            continue
        raw = (repo_root / path).read_text(encoding="utf-8")
        try:
            document = json.loads(raw)
        except json.JSONDecodeError:
            # A file the product cannot parse is not a route it could take.
            continue
        if isinstance(document, dict) and "providers" in document:
            shaped.append(path)
    assert not shaped, (
        f"these files hold a top-level 'providers' object: {shaped}. That is the "
        "shape a provider configuration has, whatever the file is called."
    )


@pytest.mark.unit
def test_the_settings_schema_has_nowhere_to_put_a_price_or_a_capability_claim(
    repo_root: Path,
) -> None:
    """The format itself cannot carry a price or a capability claim.

    **The key set is closed, and it is exactly these six.** An entry carrying
    anything else is *refused* rather than ignored, so the schema has no room
    for a price or a capability claim in the first place — which is what makes
    *"no price and no capability claim is written into the tree"* a property
    of the **format** and not only of the files that happen to be in it
    today: a configuration written tomorrow cannot carry one either.

    **The key set is read out of the tree**, not out of the installed
    package, and the reader fails loudly when it cannot find it. And a new
    key is a deliberate act: it is reviewed here rather than appearing
    because a dataclass field was added somewhere else.
    """
    accepted = _accepted_settings_keys(repo_root)
    assert accepted == set(SETTINGS_KEYS), (
        f"the settings format accepts {sorted(accepted)}; it accepts exactly "
        f"{sorted(SETTINGS_KEYS)}. A new key is a deliberate act, and this is "
        "where it is reviewed."
    )
    for key in sorted(accepted):
        lowered = key.lower()
        assert not any(word in lowered for word in PRICE_OR_CAPABILITY_WORDS), (
            f"the settings format accepts {key!r}, which is a price or a "
            "capability claim. A capability claim is a measurement (ADR-0018 "
            "§D5) and a price belongs to a table the project does not ship."
        )
    # And the format refuses them, rather than ignoring them.
    for key, value in (
        ("price", 1.25),
        ("price_usd", 1.25),
        ("cost_per_million_tokens", 3.0),
        ("capabilities", {"tool_calls": True}),
        ("supports_tools", True),
    ):
        with pytest.raises(ValueError, match="unknown provider settings key"):
            ProviderSettings.from_mapping({"protocol": "openai", "model": "m", key: value})


@pytest.mark.unit
def test_the_tree_carries_no_price_table(repo_root: Path) -> None:
    """A price can only enter the product from outside it.

    **There is no price table in the tree.** The one way a run's cost becomes
    a measured number is :meth:`RunLedger.record_price_known`, and no module
    under ``src/`` calls it — so a price is something a caller supplies from a
    table the project does not ship, and a ``max_cost_usd`` ceiling fails
    closed until they do.

    **Read by parsing rather than by matching text**: the method's own
    *definition* is in the tree, and a text search for its name would find
    that and call it a price. The ledger's own internal use is the one
    permitted call, and it is the only one.
    """
    ledger = "src/labcairn/providers/ledger.py"
    offenders: list[str] = []
    for path in sorted((repo_root / "src" / "labcairn").rglob("*.py")):
        relative = path.relative_to(repo_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in ("record_price_known", "record_cost"):
                continue
            if relative == ledger:
                continue
            offenders.append(f"{relative}:{node.lineno}: {node.func.attr}()")
    assert not offenders, "these modules supply a price, so the tree holds one: " + ", ".join(
        offenders
    )


@pytest.mark.unit
def test_the_provider_layer_names_no_endpoint_but_its_two_protocol_defaults(
    repo_root: Path,
) -> None:
    """The layer that opens a socket names exactly two remote hosts.

    **Those two are the protocol defaults**, and ADR-0019 §D2 says why they
    are not this project's supplier choice: they are *library knowledge* of
    where the two protocols' documented endpoints sit, and nothing in the
    tree selects them. The third protocol — an OpenAI-compatible endpoint —
    has **no** default, because its host is the operator's to name.

    So the set of endpoints the provider layer's *code* names is exactly
    these two, and a third one would be a route somebody wrote down.

    **Code, not prose.** A docstring is where the tree keeps the shape of a
    provider label and the name of a wire dialect; it is not a value the
    product reads. So the sweep reads **code literals only** — a docstring
    that names an endpoint is documentation of the wire, and documentation of
    the wire is vocabulary rather than a route.
    """
    named: set[str] = set()
    for path in _provider_layer_paths(repo_root):
        for _lineno, literal in _code_literals(path):
            if URL_LITERAL.match(literal):
                named.add(literal)

    assert named == set(PROTOCOL_DEFAULT_BASE_URLS), (
        f"the provider layer names {sorted(named)}; it names exactly "
        f"{sorted(PROTOCOL_DEFAULT_BASE_URLS)}. A third endpoint is a route "
        "somebody wrote down."
    )


@pytest.mark.unit
def test_a_model_can_only_enter_the_product_from_the_operator() -> None:
    """The tree holds no model id, because the tree cannot supply one.

    **The model is a required field with no default**, and a configuration
    that names no model is *refused* rather than quietly given one. So there
    is no model id for the tree to hold: the product asks the operator for
    one, and says so when the operator does not give it.

    The mutation this is written for is the one that makes the tree hold a
    model id — give ``model`` a default — and it leaves everything installed
    exactly as it was.
    """
    with pytest.raises(TypeError):
        ProviderSettings(protocol=Protocol.OPENAI)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="provider settings need a model name"):
        ProviderSettings.from_mapping({"protocol": "openai"})
    with pytest.raises(ValueError, match="provider settings need a model name"):
        ProviderSettings.from_mapping({"protocol": "openai", "model": "   "})


@pytest.mark.unit
def test_the_tracked_environment_template_carries_no_value(repo_root: Path) -> None:
    """The one file in the tree that is *about* the provider configuration is empty.

    ``.env.example`` is the tracked template for ``.env``, and it is the file
    that names the credential variables, the custom-endpoint variables, the
    default model and the ceilings. **Every value in it is empty**, and that
    is what makes it a template rather than a configuration: a model id, an
    endpoint, a price or a credential written into it would be a route — or a
    secret — in the tree.

    **Read as a template, not as a dotenv parser**: a line is a name, an
    ``=`` and a value, and the value must be empty. A comment or a blank line
    is not a variable.
    """
    path = repo_root / ".env.example"
    assert path.is_file(), "the tracked environment template is missing"

    offenders: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, _, value = stripped.partition("=")
        if value.strip():
            offenders.append(f"{number}: {name}")
    assert not offenders, (
        "these variables carry a value in the tracked template: "
        + ", ".join(offenders)
        + ". A model id, an endpoint, a price or a credential written into the "
        "template is a route in the tree, or a secret in it."
    )
