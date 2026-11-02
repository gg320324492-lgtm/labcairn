#!/usr/bin/env python3
"""Run LC-P2-14's blind evaluation.

**Dry run — the default, and the one that spends nothing:**

    python scripts/run_blind_evaluation.py --mode dry-run --out DIR

It sends one request per arm and case to a stub, writes the artefacts, the
blind packet, two synthetic sheets (every dimension ``unknown``), both
contrasts and the report. The run record says ``model: ""``,
``provider_calls: 0`` and carries a limitations sentence; the report says the
same at the top. Nothing here is a measurement of a model.

**Real run — the owner's, and refused without the owner's pieces:**

    python scripts/run_blind_evaluation.py --mode real \
        --cases cases.json --out DIR \
        --workspace-root PATH --task TASK \
        --model MODEL --protocol openai \
        --approvals approvals.json \
        --budget-max-total-tokens N

The command refuses, before constructing a provider, unless it has an owner
approval for every request and at least one budget ceiling. The provider it
builds is ``PydanticAiModelProvider`` and nothing else; that class cannot be
constructed without an ``OutboundConsent`` port, and this script does not
have a second path around it. A real run stops at ``awaiting-ratings``:
significance needs two independent raters and an arbiter.

**Scoring — after the sheets are in:**

    python scripts/run_blind_evaluation.py --mode score --run DIR \
        --rater-a SHEET_A.json --rater-b SHEET_B.json --arbiter ARBITER.json

It loads the sheets through the production loader, unblinds through the run's
map, builds the two contrasts and writes the report.

Exit codes:

* **0** — the run did what the mode says it does;
* **2** — the command refused, and the message names what is missing;
* **3** — a real run was refused by the outbound bridge mid-run;
* **1** — a fault (unreadable file, malformed sheet, and so on).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

# The runner and its modules live beside the harness, which is an importable
# top-level package only when tests/ is on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from evaluation import blind_runner

from labcairn.application.approvals import ApprovalUse
from labcairn.cli.workspace import (
    WorkspaceConfig,
    WorkspaceLocation,
    application_context,
    read_config,
)
from labcairn.core.ids import TaskId
from labcairn.core.providers.usage import Known
from labcairn.providers.budget import RunBudget
from labcairn.providers.credentials import Protocol, ProviderSettings
from labcairn.providers.errors import OutboundRefusedError
from labcairn.providers.pydantic_models import build_http_client
from labcairn.providers.usage_capture import HttpxUsageSniffer
from labcairn.security.capabilities import CapabilityId

EXIT_OK = 0
EXIT_FAULT = 1
EXIT_REFUSED = 2
EXIT_OUTBOUND_REFUSED = 3


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cases(path: Path) -> tuple[blind_runner.CaseSpec, ...]:
    document = _load_json(path)
    if not isinstance(document, Mapping):
        raise ValueError("the case file is not an object")
    return blind_runner.CaseSet.from_document(document).cases


def _load_approvals(path: Path) -> tuple[blind_runner.ApprovalGrant, ...]:
    document = _load_json(path)
    if not isinstance(document, Mapping):
        raise ValueError("the approval file is not an object")
    raw = document.get("approvals")
    if not isinstance(raw, list) or not raw:
        raise ValueError("the approval file carries no approvals")
    grants: list[blind_runner.ApprovalGrant] = []
    for one in raw:
        if not isinstance(one, Mapping):
            raise ValueError("an approval is not an object")
        for field_name in ("approval_id", "capability", "root_id", "resource_key"):
            if field_name not in one:
                raise ValueError(f"an approval carries no {field_name}")
        grant = blind_runner.ApprovalGrant(
            approval_id=UUID(str(one["approval_id"])),
            use=ApprovalUse(
                capability=CapabilityId(str(one["capability"])),
                arguments=dict(one.get("arguments", {})),
                root_id=str(one["root_id"]),
                resource_key=str(one["resource_key"]),
            ),
        )
        grants.append(grant)
    return tuple(grants)


def _load_budget(args: argparse.Namespace) -> RunBudget | None:
    ceilings: dict[str, object] = {}
    if args.budget_max_total_tokens is not None:
        ceilings["max_total_tokens"] = Known(args.budget_max_total_tokens)
    if args.budget_max_model_requests is not None:
        ceilings["max_model_requests"] = args.budget_max_model_requests
    if args.budget_max_cost_usd is not None:
        ceilings["max_cost_usd"] = Decimal(args.budget_max_cost_usd)
    if not ceilings:
        return None
    return RunBudget(**ceilings)  # type: ignore[arg-type]


def _provider_settings(args: argparse.Namespace) -> ProviderSettings:
    return ProviderSettings(
        protocol=Protocol(args.protocol),
        model=args.model,
        base_url=args.base_url,
        credential_env=args.credential_env,
    )


def _dry_run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="labcairn-blind-"))
    cases = _load_cases(Path(args.cases)) if args.cases else None
    summary = blind_runner.run_dry(out_dir=out_dir, cases=cases)
    print("LC-P2-14 blind evaluation - DRY RUN")
    print("Nothing was sent to a model; every rating is the unknown label.")
    print(f"  out          : {summary.out_dir}")
    print(f"  status       : {summary.status}")
    print(f"  provider calls: {summary.provider_calls}")
    print(f"  stub calls   : {summary.stub_calls}")
    print(f"  split clean  : {summary.split_clean}")
    for report in summary.contrasts:
        for row in report.rows:
            verdict = row.verdict
            print(
                f"  {report.contrast:8s} {row.dimension:28s} "
                f"wins={verdict.counts.wins} losses={verdict.counts.losses} "
                f"ties={verdict.counts.ties} significant={verdict.significant}"
            )
    return EXIT_OK


def _real_run(args: argparse.Namespace) -> int:
    if not args.cases or not args.workspace_root or not args.task or not args.model:
        print(
            "refused: a real run needs --cases, --workspace-root, --task and --model",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    cases = _load_cases(Path(args.cases))
    budget = _load_budget(args)
    approvals = _load_approvals(Path(args.approvals)) if args.approvals else ()
    required = len(cases) * 5
    if len(approvals) < required:
        print(
            f"refused: the run has {required} requests (5 arms x {len(cases)} cases) "
            f"but the owner supplied {len(approvals)} approvals; one approval "
            "covers one request, and the driver will not start a run it cannot "
            "finish",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    sniffer = _build_sniffer()
    problems = blind_runner.missing_real_requirements(
        approvals=len(approvals),
        budget=budget,
        model=args.model,
        usage_capture=sniffer,
    )
    if problems:
        for problem in problems:
            print(f"refused: {problem}", file=sys.stderr)
        return EXIT_REFUSED
    if sniffer is None:  # unreachable after missing_real_requirements, kept explicit
        return EXIT_REFUSED

    location = WorkspaceLocation(root=Path(args.workspace_root).expanduser().resolve())
    config: WorkspaceConfig = read_config(location)
    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="labcairn-blind-"))
    settings = _provider_settings(args)
    http_client = build_http_client(settings, sniffer=sniffer)
    try:
        with application_context(location, config, TaskId(args.task)) as context:
            consent = blind_runner.ConsumingApprovals(context, approvals)
            provider = blind_runner.build_real_provider(
                settings,
                consent=consent,
                budget=budget,
                usage_capture=sniffer,
                http_client=http_client,
            )
            summary = blind_runner.run_real(
                provider=provider,
                out_dir=out_dir,
                model=args.model,
                budget=_budget_label(budget),
                cases=cases,
            )
    except OutboundRefusedError as error:
        print(f"refused by the outbound bridge: {error}", file=sys.stderr)
        return EXIT_OUTBOUND_REFUSED
    print("LC-P2-14 blind evaluation - REAL RUN")
    print(f"  out           : {summary.out_dir}")
    print(f"  status        : {summary.status}")
    print(f"  provider calls: {summary.provider_calls}")
    print("  ratings       : not scored; two independent raters and an arbiter are needed")
    return EXIT_OK


def _score(args: argparse.Namespace) -> int:
    if not args.run or not args.rater_a or not args.rater_b:
        print(
            "refused: scoring needs --run, --rater-a and --rater-b",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    summary = blind_runner.run_score(
        run_dir=Path(args.run),
        rater_a=Path(args.rater_a),
        rater_b=Path(args.rater_b),
        arbiter=Path(args.arbiter) if args.arbiter else None,
        out_dir=Path(args.out) if args.out else None,
    )
    print("LC-P2-14 blind evaluation - SCORED")
    print(f"  out    : {summary.out_dir}")
    print(f"  status : {summary.status}")
    for report in summary.contrasts:
        for row in report.rows:
            verdict = row.verdict
            print(
                f"  {report.contrast:8s} {row.dimension:28s} "
                f"wins={verdict.counts.wins} losses={verdict.counts.losses} "
                f"ties={verdict.counts.ties} significant={verdict.significant}"
            )
    return EXIT_OK


def _budget_label(budget: RunBudget | None) -> str:
    if budget is None:
        return "unbounded"
    parts: list[str] = []
    if budget.max_total_tokens is not None:
        parts.append(f"max_total_tokens={budget.max_total_tokens}")
    if budget.max_model_requests is not None:
        parts.append(f"max_model_requests={budget.max_model_requests}")
    if budget.max_cost_usd is not None:
        parts.append(f"max_cost_usd={budget.max_cost_usd}")
    return ", ".join(parts)


def _build_sniffer() -> HttpxUsageSniffer | None:
    """The one usage sniffer the run shares between its client and its capture.

    The import is deferred so ``--help`` works in an environment where the
    provider extras are not installed; a missing extra is a refusal, not a
    traceback. The same object must become both the HTTP transport and the
    provider's ``usage_capture``: two captures would let the run report a
    ``Known`` count the probe could not confirm.
    """
    try:
        import httpx
    except ImportError:
        return None
    return HttpxUsageSniffer(httpx.AsyncHTTPTransport())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--mode",
        choices=(blind_runner.MODE_DRY_RUN, blind_runner.MODE_REAL, blind_runner.MODE_SCORE),
        default=blind_runner.MODE_DRY_RUN,
        help="dry-run (default), real, or score",
    )
    parser.add_argument("--out", help="output directory (default: a fresh temporary directory)")
    parser.add_argument("--cases", help="a case-set JSON file (real mode requires it)")
    parser.add_argument("--run", help="a completed run directory (score mode)")
    parser.add_argument("--rater-a", help="rater A's sheet (score mode)")
    parser.add_argument("--rater-b", help="rater B's sheet (score mode)")
    parser.add_argument("--arbiter", help="the arbiter's decisions (score mode)")
    parser.add_argument(
        "--workspace-root", help="the workspace the approvals belong to (real mode)"
    )
    parser.add_argument("--task", help="the task id the approvals belong to (real mode)")
    parser.add_argument("--model", help="the declared model (real mode)")
    parser.add_argument(
        "--protocol",
        choices=tuple(protocol.value for protocol in Protocol),
        default=Protocol.OPENAI.value,
        help="the provider wire dialect (real mode)",
    )
    parser.add_argument("--base-url", help="the endpoint (openai_compatible requires it)")
    parser.add_argument("--credential-env", help="the environment variable holding the key")
    parser.add_argument("--approvals", help="the owner's approval records (real mode)")
    parser.add_argument("--budget-max-total-tokens", type=int, help="a token ceiling (real mode)")
    parser.add_argument(
        "--budget-max-model-requests", type=int, help="a request ceiling (real mode)"
    )
    parser.add_argument("--budget-max-cost-usd", help="a cost ceiling (real mode)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == blind_runner.MODE_DRY_RUN:
            return _dry_run(args)
        if args.mode == blind_runner.MODE_REAL:
            return _real_run(args)
        return _score(args)
    except blind_runner.RealRunRefusedError as error:
        print(f"refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except OutboundRefusedError as error:
        print(f"refused by the outbound bridge: {error}", file=sys.stderr)
        return EXIT_OUTBOUND_REFUSED
    except (ValueError, OSError) as error:
        print(f"fault: {error}", file=sys.stderr)
        return EXIT_FAULT
    except RuntimeError as error:
        # A workspace that cannot be opened is a refusal, not a traceback: the
        # real run has not sent anything at that point.
        print(f"refused: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
