#!/usr/bin/env python3
"""Run the real-provider smoke that LC-P1-03's acceptance requires.

**This spends money.** It sends live requests to a provider endpoint and it
exists because the work order says *"real smoke on at least one provider"*, not
because a mock said so. Run it only with the project owner's authorisation and
a credential issued for the purpose.

Set these before running::

    export LABCAIRN_PROVIDER_SMOKE_KEY='...'
    export LABCAIRN_SMOKE_PROTOCOL='openai'      # openai | anthropic | openai_compatible
    export LABCAIRN_SMOKE_MODEL='gpt-4.1-mini'
    export LABCAIRN_SMOKE_BASE_URL='...'         # required for openai_compatible
    export LABCAIRN_SMOKE_TIMEOUT='30'           # optional

Design choices that are not incidental:

- **No credential fallback.** If ``LABCAIRN_PROVIDER_SMOKE_KEY`` is unset the
  script refuses. It does not look at other environment variables, because a
  credential merely present on a developer's machine is not one issued for
  spending — that is the rule the skipped test states, and this script is where
  it becomes real.
- **The credential is never printed.** ``Credential.reveal()`` is confined to
  one module and an exhaustive test enforces it; this script never calls it. The
  output carries the endpoint fingerprint instead, which is derived from the URL
  and the model, not from the key.
- **The output is paste-ready.** A smoke result goes into an issue; a
  ProbeRecord's ``to_wire`` form is what gets pasted.

Usage::

    uv run python scripts/provider_smoke.py
    uv run python scripts/provider_smoke.py --dry-run   # validate config, send nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Final

KEY_VAR: Final = "LABCAIRN_PROVIDER_SMOKE_KEY"
PROTOCOL_VAR: Final = "LABCAIRN_SMOKE_PROTOCOL"
MODEL_VAR: Final = "LABCAIRN_SMOKE_MODEL"
BASE_URL_VAR: Final = "LABCAIRN_SMOKE_BASE_URL"
TIMEOUT_VAR: Final = "LABCAIRN_SMOKE_TIMEOUT"

EXIT_OK: Final = 0
EXIT_NOT_CONFIGURED: Final = 2
EXIT_UNREACHABLE: Final = 3


def _fail(code: int, message: str, *detail: str) -> int:
    print(f"\n{code}: {message}", file=sys.stderr)
    for line in detail:
        print(f"   {line}", file=sys.stderr)
    return code


def _build_settings():
    """Construct ProviderSettings from the environment, or explain what is missing."""
    from labcairn.providers.credentials import Credential
    from labcairn.providers.pydantic_models import Protocol, ProviderSettings, smoke_test

    if not os.environ.get(KEY_VAR):
        return None, _fail(
            EXIT_NOT_CONFIGURED,
            f"{KEY_VAR} is not set, so there is no credential to use.",
            "This script will not fall back to another environment variable: a key",
            "happening to exist on this machine is not one issued for spending.",
        )

    protocol_raw = os.environ.get(PROTOCOL_VAR, "openai").strip().lower()
    try:
        protocol = Protocol(protocol_raw)
    except ValueError:
        return None, _fail(
            EXIT_NOT_CONFIGURED,
            f"{PROTOCOL_VAR}={protocol_raw!r} is not a protocol.",
            "Expected one of: " + ", ".join(p.value for p in Protocol),
        )

    model = os.environ.get(MODEL_VAR, "").strip()
    if not model:
        return None, _fail(
            EXIT_NOT_CONFIGURED,
            f"{MODEL_VAR} is not set.",
            "A probe needs a model name; guessing one would test an endpoint we",
            "never meant to test.",
        )

    base_url = os.environ.get(BASE_URL_VAR, "").strip() or None
    if protocol is Protocol.OPENAI_COMPATIBLE and not base_url:
        return None, _fail(
            EXIT_NOT_CONFIGURED,
            f"{BASE_URL_VAR} is required for the openai_compatible protocol.",
            "A custom endpoint without its URL has nothing to probe.",
        )

    try:
        timeout = float(os.environ.get(TIMEOUT_VAR, "30"))
    except ValueError:
        return None, _fail(EXIT_NOT_CONFIGURED, f"{TIMEOUT_VAR} is not a number.")

    credential = Credential.of(os.environ[KEY_VAR], source=KEY_VAR)
    settings = ProviderSettings(
        protocol=protocol,
        model=model,
        base_url=base_url,
        credential_env=KEY_VAR,
        timeout_s=timeout,
    )
    return (smoke_test, settings, credential), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and print what would be sent. Sends nothing.",
    )
    args = parser.parse_args()

    print("LabCairn — real-provider smoke (LC-P1-03 acceptance)")
    print("This sends live requests and costs money.\n")

    built, error = _build_settings()
    if error is not None:
        return error
    smoke_test, settings, credential = built  # type: ignore[misc]

    print(f"  protocol   : {settings.protocol.value}")
    print(f"  model      : {settings.model}")
    print(f"  base_url   : {settings.base_url or '(provider default)'}")
    print(f"  credential : {credential.source} (value never printed)")

    if args.dry_run:
        print("\nDRY RUN — nothing was sent.")
        return EXIT_OK

    print("\nSending live capability probes. This costs money.\n")
    try:
        result = smoke_test(settings, credential=credential)
    except Exception as exc:
        print(f"\nProbe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "\nThis says the endpoint was not usable from here. It does not say\n"
            "whether the model supports the capability, only that nothing came back.",
            file=sys.stderr,
        )
        return EXIT_UNREACHABLE

    print("Paste-ready result:\n")
    print("```json")
    print(json.dumps(dict(result), indent=2, ensure_ascii=False, default=str))
    print("```")

    print(
        "\nWhat this does NOT establish:",
        file=sys.stderr,
    )
    for line in (
        "  - it does not verify that budgets account for real spend; Phase 1 has",
        "    no price table, so the result carries no cost figure and a",
        "    max_cost_usd ceiling would fail closed against it",
        "  - it does not exercise multi-turn tool calling, retry, or cancellation",
        "    over a real network",
        "  - it verifies how this endpoint responded today, not that LabCairn is",
        "    correct in production",
    ):
        print(line, file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
