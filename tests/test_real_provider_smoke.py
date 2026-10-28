"""The real-model smoke — the protocol's fifth gate class, against a live endpoint.

This file is the artifact `tests/evaluation/manifest.py:REAL_MODEL_SMOKE_FILE`
names. Before it existed, the class had no witness at all: the harness reported
**NOT RUN** because there was nothing to run, and the only live probe this
project ever made was a hand-call recorded in a merge message. A gate class that
no file carries is not a class that is skipped — it is a class that cannot be
run, which is a different and worse thing to hand over.

What this file is, and what it is not
-------------------------------------

It is the **only** place in the suite that reads the ambient environment, and it
reads exactly four configuration variables plus one optional output path. It
skips when the key or the model is absent — which is every **required** check in
this repository, by design: a check that can only pass where a secret exists is a
check branch protection would wait on forever. The job that does name them is
``.github/workflows/provider-smoke.yml``, and that job fails rather than skipping
when a name is missing, because a scheduled paid probe that reports green without
probing anything is the failure mode this repository keeps finding.

It is **not** a way to use a credential that happens to be on a machine. The
project's rule from LC-P1-03 onward is that the owner supplies one for this
purpose; a variable named ``ANTHROPIC_API_KEY`` in a developer's shell is not
that supply, and :func:`live_settings` is what enforces the difference.

The witnesses for that predicate live in
:mod:`tests.test_provider_credentials`, which is filed under the unit class. A
rule that gates a class may not be tested only inside that class: the offline
run would then never check the rule that keeps it offline.

A test that could inherit a developer's key is a test that eventually prints
one, or spends one.

Running it
----------

::

    LABCAIRN_PROVIDER_SMOKE_KEY=... \
    LABCAIRN_PROVIDER_SMOKE_MODEL=... \
    LABCAIRN_PROVIDER_SMOKE_BASE_URL=... \
    uv run pytest tests/test_real_provider_smoke.py

No code change, and no model name invented: a key without a declared model is a
skip, because a probe against an endpoint's default model names no model and the
record would then be unusable as evidence of anything.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from labcairn.providers.capabilities import ALL_CAPABILITIES
from labcairn.providers.credentials import Protocol, ProviderSettings

#: The variables the live smoke reads. Named here so the repository can say
#: which ones it reads, and so the offline witnesses below can pass them
#: explicitly instead of setting the environment of the process running the suite.
SMOKE_KEY_ENV = "LABCAIRN_PROVIDER_SMOKE_KEY"
SMOKE_MODEL_ENV = "LABCAIRN_PROVIDER_SMOKE_MODEL"
SMOKE_PROTOCOL_ENV = "LABCAIRN_PROVIDER_SMOKE_PROTOCOL"
SMOKE_BASE_URL_ENV = "LABCAIRN_PROVIDER_SMOKE_BASE_URL"
#: Optional. Where a live run writes its probe record, outside the repository.
SMOKE_RECORD_ENV = "LABCAIRN_PROVIDER_SMOKE_RECORD"

#: The protocol a live run uses when the operator names none. This is the one
#: this project has ever probed, and the Anthropic SDK appends ``/v1/messages``
#: to the base URL — so an Anthropic-compatible gateway is configured by giving
#: the gateway's own prefix, not a ``/v1`` suffix.
SMOKE_DEFAULT_PROTOCOL = Protocol.ANTHROPIC


def live_settings(environ: Mapping[str, str]) -> ProviderSettings | None:
    """The live smoke's configuration, or None when it must not run.

    Takes the mapping as an argument rather than reading :data:`os.environ`
    itself, so the rule can be tested without spending money or touching an
    endpoint: what matters is *which* variables decide the run, and what happens
    when they are absent.

    **No model name is invented.** A run against whatever the endpoint happens to
    default to is not a probe of a declared model, and the purpose of this class
    is a record that names one. So a key without a model is a skip, not a guess.

    A credential that merely happens to be in the machine's environment —
    ``ANTHROPIC_API_KEY``, say — does not enable it either. LC-P1-03's rule was
    that the project must not spend a key it was never given, and that rule has
    to sit in the code that decides whether to run rather than in prose.
    """
    key = environ.get(SMOKE_KEY_ENV, "").strip()
    model = environ.get(SMOKE_MODEL_ENV, "").strip()
    if not key or not model:
        return None
    protocol_name = environ.get(SMOKE_PROTOCOL_ENV, "").strip() or SMOKE_DEFAULT_PROTOCOL.value
    base_url = environ.get(SMOKE_BASE_URL_ENV, "").strip() or None
    return ProviderSettings(
        protocol=Protocol(protocol_name),
        model=model,
        base_url=base_url,
        credential_env=SMOKE_KEY_ENV,
    )


@pytest.mark.requires_provider
@pytest.mark.skipif(
    live_settings(os.environ) is None,
    reason=(
        "NOT RUN. Needs the project owner's authorisation to spend money, expressed as "
        f"{SMOKE_KEY_ENV} and {SMOKE_MODEL_ENV} (optionally {SMOKE_PROTOCOL_ENV} and "
        f"{SMOKE_BASE_URL_ENV}). The required checks name none of them by design; "
        ".github/workflows/provider-smoke.yml names all four and fails rather "
        "than skipping when they are missing."
    ),
)
def test_real_provider_smoke_records_capabilities_and_usage() -> None:
    """One live capability probe against the endpoint the owner named.

    The procedure is :func:`~labcairn.providers.pydantic_models.smoke_test` and
    the configuration is :func:`_live_settings`, so running this is supplying the
    variables rather than editing the test.

    What it asserts when it runs: the record names the model and protocol it
    probed, every declared capability got an outcome, and no outcome is outside
    the vocabulary. An outcome of ``unsupported`` for the structured-output pair
    is **this build's** answer — pydantic-ai's profile can refuse before anything
    is sent, and the probe records the class name rather than attributing the
    refusal to the endpoint. That is why §2.14 calls the capability unmeasured
    rather than absent.
    """
    from labcairn.providers.pydantic_models import smoke_test

    settings = live_settings(os.environ)
    assert settings is not None, "the skipif and the body must agree"

    result = smoke_test(settings, environ=os.environ)

    outcomes = result["outcomes"]
    assert isinstance(outcomes, dict)
    assert outcomes
    assert set(outcomes) == {capability.value for capability in ALL_CAPABILITIES}, (
        f"a capability went unprobed: {sorted(set(outcomes))}"
    )
    for outcome in outcomes.values():
        assert outcome in {"ok", "unsupported", "unverified", "refused"}
    assert result["model"] == settings.model, (
        "the record must name the model that was probed, not one it inferred"
    )
    assert result["protocol"] == settings.protocol_label

    record_path = os.environ.get(SMOKE_RECORD_ENV, "").strip()
    if record_path:
        Path(record_path).write_text(
            json.dumps(dict(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
