"""LC-P2-18's our-side runner: the LC-P2-01 model-call path over the package's three task faces.

**What this script is.** The runbook's Step 3 (``docs/acceptance/LC-P2-18-machinery.md``
§4): drive the package's three task faces through the product's own model-call
path — :func:`labcairn.application.model_request.request_model`, under the
consent layer's two gates in their order — and write the raw artifacts in the
layout ``competitor_paperqa_run.ArtifactLayout`` describes, so the aligner reads
both sides with one walk. The numeric face's artifacts carry their per-cell
outcomes under ``numeric-cell-exactness``; the abstention case's artifact
carries the verbatim answer; the recovery face's four cases are the product's
real crash matrix, executed with the fault armed at each crash point, each
recording the boolean it observed beside a ``present`` surface declaration.

**This spends money.** Every model call goes out to the provider named in the
workspace's ``providers.json`` and consumes a single-use approval. The script is
gated exactly as the competitor side's runner is gated: without
``--approval`` pointing at the owner's approval file it refuses before anything
is built. Each call's own budget carries a request ceiling, and the run carries
a call ceiling of its own — a ceiling the path enforces, not hope.

**The keys never reach the model.** A case's prompt is its material text and its
question text, plus a fixed output-format instruction that is part of this
side's calling protocol and is recorded in the artifacts. The answer keys are
read only after the call, by the scoring functions, which is where scoring
lives.

**The scoring is mechanical and recorded.** The numeric face's cells are the
per-``(selection, group, statistic)`` value matches the key addresses; a value
the model did not give is a miss, not an omission from the denominator. A
selection the key declares refused produces no cells — its behaviour is
recorded beside the cells, not folded into a number. Values compare with
``math.isclose(rel_tol=1e-9, abs_tol=1e-12)``, a tolerance this record states
rather than buries.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "tests"))
sys.path.insert(0, str(REPOSITORY / "tests" / "evaluation"))

import recovery_support  # noqa: E402,F401  (module import arms the sys.path for its siblings)
from evaluation.competitor_package import (  # noqa: E402
    package_manifest_sha256,
    task_case_files,
    validate_package,
)
from evaluation.competitor_paperqa_run import (  # noqa: E402
    ArtifactLayout,
    LiveRunNotAuthorizedError,
    require_live_authorization,
)
from evaluation.paperqa_adapter import render_fixture  # noqa: E402
from recovery_support import NULL_SINK, RecordingSink, arm, build_scenario, hash_bytes  # noqa: E402

from labcairn.application.approvals import (  # noqa: E402
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.context import ApplicationContext  # noqa: E402
from labcairn.application.model_request import ModelInvocation, request_model  # noqa: E402
from labcairn.application.tasks import create_task  # noqa: E402
from labcairn.core.ids import ApprovalId  # noqa: E402
from labcairn.core.providers.protocol import ModelRequest  # noqa: E402
from labcairn.core.providers.usage import Known  # noqa: E402
from labcairn.db.migrations import upgrade_to_head  # noqa: E402
from labcairn.db.repository import TaskStore  # noqa: E402
from labcairn.db.session import create_db_engine, create_session_factory  # noqa: E402
from labcairn.providers.adapter import PydanticAiModelProvider  # noqa: E402
from labcairn.providers.budget import RunBudget  # noqa: E402
from labcairn.providers.credentials import (  # noqa: E402
    load_credential,
    load_providers_config,
)
from labcairn.providers.pydantic_models import (  # noqa: E402
    build_http_client,
    build_model,
    make_sniffer,
)
from labcairn.reports.receipt import ArtifactKind  # noqa: E402
from labcairn.runtime.lifecycle import TaskGoal  # noqa: E402
from labcairn.security.approval import ApprovalLedger  # noqa: E402
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs  # noqa: E402
from labcairn.security.permissions import Grant  # noqa: E402
from labcairn.security.policy import (  # noqa: E402
    Permission,
    PermissionPolicy,
    Rule,
)

NUMERIC_FACE = "numeric-extraction"
ABSTENTION_FACE = "unsupported-claim-detection"
RECOVERY_FACE = "recovery-correctness"

RESOURCE_KEY = "outputs/report.md"
RESOURCE_BODY = b"# Findings\n\nThe observation holds.\n"
CAPABILITY = "labcairn.artifact.write"

#: The output-format instruction appended to every prompt. It is this side's
#: calling protocol — the same material, the same question text, and a format
#: the scorer can parse mechanically. Recorded here rather than invented
#: per-call, so the run's prompts differ from the competitor's in exactly one
#: declared way.
FORMAT_INSTRUCTION = (
    "\n\nAnswer with one JSON object and nothing before or after it. Use the "
    'shape {"selections": [{"name": "<the question\'s own item number>", '
    '"values": {"<group name, or "overall" where the question does not '
    'group>": {"sum": <number>, "min": <number>, "max": <number>, "mean": '
    '<number>, "median": <number>, "stdev_population": <number>, '
    '"stdev_sample": <number>}}}]}. Give every statistic the question asks '
    "for. If a stated computation cannot be performed on the table as given, "
    "leave that selection's values as an empty object and explain inside "
    '"notes". For a question that is not a computation, use {"answer": <the '
    'value or null>, "notes": "<why>"}.'
)


class OurSideError(RuntimeError):
    """The our-side run could not proceed; nothing further will be spent."""


# --------------------------------------------------------------------------- #
# the workspace: provider config, migrated store, one task, one policy
# --------------------------------------------------------------------------- #

PILOT_PROVIDERS = Path("E:/labcairn-local/pilot-ws/providers.json")


def build_workspace(workspace: Path, package_dir: Path) -> ApplicationContext:
    """A migrated store, a task whose source roots are the package's materials, a policy."""
    workspace.mkdir(parents=True, exist_ok=True)
    providers_path = workspace / "providers.json"
    if not providers_path.exists():
        if not PILOT_PROVIDERS.is_file():
            raise OurSideError(
                f"no operator provider configuration at {PILOT_PROVIDERS}; "
                "the tree carries no supplier and there is no default"
            )
        providers_path.write_bytes(PILOT_PROVIDERS.read_bytes())

    db_path = workspace / "labcairn.db"
    if not db_path.exists():
        upgrade_to_head(db_path)
    engine = create_db_engine(db_path)
    session = create_session_factory(engine)()

    numeric_fixtures = package_dir / "tasks" / NUMERIC_FACE / "fixtures"
    abstention_material = package_dir / "tasks" / ABSTENTION_FACE / "material"
    # A source root must sit inside the workspace the user selected, so the
    # package's material is copied in — the prompts are still built from the
    # package's own bytes, and the copies exist so the consent layer's path
    # canonicalisation sees material the workspace governs.
    task_root = workspace / "task"
    task_root.mkdir(exist_ok=True)
    materials_root = task_root / "materials"
    source_dirs = []
    for name, origin in (
        ("numeric-fixtures", numeric_fixtures),
        ("abstention-material", abstention_material),
    ):
        if origin.is_dir():
            copy = materials_root / name
            copy.mkdir(parents=True, exist_ok=True)
            for item in origin.iterdir():
                target = copy / item.name
                if not target.exists() or target.read_bytes() != item.read_bytes():
                    target.write_bytes(item.read_bytes())
            source_dirs.append(copy)

    created = create_task(
        store=TaskStore(session),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=task_root,
        title="LC-P2-18 competitor baseline, our side",
        goal=TaskGoal(
            objective="A real-model run of the package's three task faces.",
            success_criterion="Raw artifacts the aligner can score.",
        ),
        source_dirs=tuple(source_dirs),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=TaskStore(session),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _settings(workspace: Path) -> tuple[Any, str]:
    """The provider settings the workspace's own providers.json declares."""
    providers_path = workspace / "providers.json"
    providers = load_providers_config(providers_path)
    name = next(iter(providers))
    return providers[name], name


# --------------------------------------------------------------------------- #
# the material gate: the grants the request is judged against
# --------------------------------------------------------------------------- #


def _grants(subject_ref: str, at: datetime) -> list[Grant]:
    """The material-purpose grants the transmit check is judged against.

    The scope admits the task's material; the destination is the endpoint the
    workspace's own ``providers.json`` names. A request whose material or
    destination falls outside this grant is refused by the transmit check
    before the approval is consumed.
    """
    return [
        Grant(
            grant_id="lc-p2-18-transmit-grant",
            subject_ref=subject_ref,
            permission="external_transmit",
            purpose="transmit",
            scope=f"{subject_ref}/**",
            destination="api.minimax.cn",
            granted_by="owner (2026-11-04, session authorization)",
            granted_at=at,
            expires_at=None,
            state="active",
            withdrawn_at=None,
            withdrawn_by=None,
            withdrawal_reason=None,
        )
    ]


# --------------------------------------------------------------------------- #
# the model call: one approval, one call, one record
# --------------------------------------------------------------------------- #


class DecisionAlreadyMade:
    """The consent port for a send inside ``request_model``: the decision was made before send ran.

    ``request_model`` runs every gate — the budget preflight, the transmit
    check, the approval's own consume — **before** it calls ``send``, so by
    the time the provider asks "may this request leave?", the application
    layer has already answered it and spent the single-use approval that
    answer cost. This port hands that fact over without consuming anything:
    a second consume here would spend a second approval for one wire
    request, which is not the single-use guarantee but its corruption.
    """

    def __init__(self, approval_id: ApprovalId) -> None:
        self._approval_id = approval_id

    def require(self, request: ModelRequest) -> None:
        """Permit: the decision belongs to the path that called send."""


def ask_model(
    context: ApplicationContext,
    workspace: Path,
    *,
    prompt: str,
    material_ref: str,
    root_id: str,
    purpose: str,
) -> tuple[str, dict[str, Any]]:
    """One model call through the LC-P2-01 path, and what the wire carried.

    The call is gated twice — the material gate's transmit check runs first,
    and only a permitted request consumes the approval. A fresh single-use
    approval is requested and granted for every call, because
    ``OutboundApproval`` is spent on the first ``require`` and that is the
    single-use guarantee, not a limitation.
    """
    settings, provider_name = _settings(workspace)
    use = ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider=provider_name,
            model=settings.model,
            path=material_ref,
            excerpts=(),
            purpose=purpose,
        ).model_dump(),
        root_id=root_id,
        resource_key=material_ref,
    )
    now = datetime.now(UTC)
    requested = request_approval(
        context, ApprovalRequest(use=use, expires_at=now + timedelta(hours=1)), now=now
    )
    approval_id: ApprovalId = requested.approval.approval_id
    grant_approval(context, approval_id, now=now)

    credential = load_credential(settings)
    sniffer = make_sniffer()
    http_client = build_http_client(settings, sniffer=sniffer)
    model = build_model(settings, credential=credential, http_client=http_client)
    usage_seen: list[Any] = []

    def send() -> ModelInvocation:
        provider = PydanticAiModelProvider(
            model=model,
            consent=DecisionAlreadyMade(approval_id),
            usage_capture=sniffer,
            budget=RunBudget(max_model_requests=1),
            timeout_s=settings.timeout_s,
            provider_label=provider_name,
        )
        response = provider.send(ModelRequest(prompt=prompt))
        usage_seen.append(response.usage)
        return ModelInvocation(
            answer=response.text,
            provider=provider_name,
            model=settings.model,
            exchanges=tuple(record.to_wire() for record in provider.exchanges()),
            credential_fingerprint=credential.fingerprint,
        )

    answer = request_model(
        context,
        approval_id,
        _grants(str(context.task_id), now),
        use=use,
        subject_ref=str(context.task_id),
        destination=_destination(settings),
        purpose="transmit",
        at=now,
        send=send,
        budget=RunBudget(max_model_requests=1),
    )
    usage = usage_seen[0] if usage_seen else None
    tokens: dict[str, int | None] = {}
    if usage is not None:
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(usage, name, None)
            tokens[name] = value.value if isinstance(value, Known) else None
    return answer.answer, {"model": settings.model, "tokens": tokens}


def _destination(settings: Any) -> str:
    """The endpoint a permitted request goes to, from the operator's own settings."""
    base = getattr(settings, "effective_base_url", None) or getattr(settings, "base_url", "")
    return str(base).split("//")[-1].split("/")[0]


# --------------------------------------------------------------------------- #
# the numeric face: material, question, answer, per-cell outcomes
# --------------------------------------------------------------------------- #


def _numeric_material(package_dir: Path, fixture: str) -> str:
    """The fixture's bytes, rendered the way the competitor's adapter renders them."""
    raw = (package_dir / "tasks" / NUMERIC_FACE / "fixtures" / fixture).read_bytes()
    if fixture.endswith(".xlsx"):
        rendered = render_fixture(fixture, spreadsheets={fixture: raw})
        return rendered if isinstance(rendered, str) else str(rendered)
    return raw.decode("utf-8")


def expand_key_cells(fixture: str, key: dict[str, Any]) -> tuple[list[dict[str, Any]], list[int]]:
    """The cells the key addresses, and the selections it declares refused.

    A cell is one ``(selection, group, statistic)`` triple the question asks
    the model to compute; a refused selection produces no cells — its
    expected behaviour is an abstention, recorded beside the cells rather
    than folded into the exactness denominator.
    """
    cells: list[dict[str, Any]] = []
    refusals: list[int] = []
    for index, described in enumerate(key.get("selections", [])):
        expect = described.get("expect", {})
        if not isinstance(expect, dict):
            continue
        if expect.get("outcome") == "refused":
            refusals.append(index)
            continue
        statistics = expect.get("statistics", {})
        if not isinstance(statistics, dict):
            continue
        grouped = all(isinstance(v, dict) for v in statistics.values()) if statistics else False
        if grouped:
            groups = {str(k): dict(v) for k, v in statistics.items() if isinstance(v, dict)}
        else:
            flat = {
                str(k): float(v)
                for k, v in statistics.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            groups = {"overall": flat} if flat else {}
        for group, table in sorted(groups.items()):
            for statistic, expected in sorted(table.items()):
                if isinstance(expected, bool) or not isinstance(expected, (int, float)):
                    continue
                cells.append(
                    {
                        "cell": f"{fixture}:{index}:{group}:{statistic}",
                        "selection": index,
                        "group": group,
                        "statistic": statistic,
                        "expected": float(expected),
                    }
                )
    return cells, refusals


def _outermost_json(text: str) -> dict[str, Any] | None:
    """The first balanced JSON object in the text, or None."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for position in range(start, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : position + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def parse_model_values(answer_text: str) -> dict[str, dict[str, dict[str, float]]]:
    """The selections the answer names, as ``name -> group -> statistic -> value``.

    A value the answer does not give in parseable shape is a miss at scoring
    time, not an error here — the verbatim answer stays in the artifact for a
    reviewer to read.
    """
    parsed = _outermost_json(answer_text)
    if parsed is None:
        return {}
    selections = parsed.get("selections")
    if not isinstance(selections, list):
        return {}
    values: dict[str, dict[str, dict[str, float]]] = {}
    for entry in selections:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        raw_values = entry.get("values", {})
        if not isinstance(raw_values, dict):
            continue
        table: dict[str, dict[str, float]] = {}
        for group, stats in raw_values.items():
            if not isinstance(stats, dict):
                continue
            clean: dict[str, float] = {}
            for statistic, value in stats.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                clean[str(statistic)] = float(value)
            table[str(group).strip()] = clean
        values[name] = table
    return values


def _lookup(
    values: dict[str, dict[str, dict[str, float]]],
    selection: int,
    group: str,
    statistic: str,
) -> float | None:
    """The model's value for one cell, matched on the question's own numbering."""
    wanted = str(selection + 1)
    for name, table in values.items():
        normalised = re.sub(r"\s+", "", name)
        if normalised != wanted and not normalised.startswith((wanted + ":", wanted + "(")):
            continue
        groups = table.get(group) or table.get("overall")
        if groups is None and len(table) == 1:
            groups = next(iter(table.values()))
        if groups is None:
            continue
        value = groups.get(statistic)
        if isinstance(value, float):
            return value
    return None


def score_numeric_case(
    fixture: str, key: dict[str, Any], answer_text: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The per-cell outcomes the model's answer produced, and the refusal record."""
    cells_template, refusals = expand_key_cells(fixture, key)
    values = parse_model_values(answer_text)
    cells: list[dict[str, Any]] = []
    for template in cells_template:
        given = _lookup(values, template["selection"], template["group"], template["statistic"])
        ok = given is not None and math.isclose(
            given, template["expected"], rel_tol=1e-9, abs_tol=1e-12
        )
        cells.append({"cell": template["cell"], "ok": ok})
    refusal_notes = []
    for index in refusals:
        offered = any(
            _lookup(values, index, "overall", statistic) is not None for statistic in _STATISTICS
        )
        refusal_notes.append(
            {
                "selection": index,
                "model_gave_values": offered,
                "expected": "an abstention with a reason, not an invented value",
            }
        )
    return cells, {"refused_selections": refusal_notes}


#: The statistics the question template asks for, in its own order.
_STATISTICS = (
    "sum",
    "min",
    "max",
    "mean",
    "median",
    "stdev_population",
    "stdev_sample",
)


# --------------------------------------------------------------------------- #
# the recovery face: the real crash matrix, executed
# --------------------------------------------------------------------------- #


def run_recovery_case(env: Any, scratch: Path, point: Any) -> bool:
    """One crash window, run and judged against the invariant its package key states.

    Every case arms the fault at its
    :class:`~labcairn.recovery.contracts.CrashPoint` inside the live execute
    path, restarts the store, and observes what recovery then makes true. No
    model is called: recovery is the product's own transactional machinery.
    """
    scenario = build_scenario(env, scratch / point.value)
    target = scenario.root.joinpath(*RESOURCE_KEY.split("/"))
    counter = scenario.counter()
    effect = counter.plan(RESOURCE_KEY, RESOURCE_BODY)
    # The notify window fires where a real client would be told, so the
    # after-confirm case needs a sink that can receive one; the other windows
    # sit before the notification and a null sink is what the matrix passes.
    sink = RecordingSink() if point.value == "after_confirm_before_notify" else NULL_SINK
    try:
        scenario.executor(faults=arm(point), sink=sink).execute(
            scenario.task_id,
            scenario.run_id,
            scenario.stage_id,
            capability=CAPABILITY,
            effect=effect,
            args={"kind": "report"},
            kind=ArtifactKind.REPORT,
        )
        return False  # the fault never fired; the case did not run
    except BaseException:
        pass  # InjectedCrash is a BaseException by design; the crash is the case

    after = scenario.restart()
    recovery = after.recovery()
    operation_id = _sole_operation_id(after)
    if operation_id is None:
        return False

    if point.value == "before_attempted_commit":
        # Nothing may exist, and the replay writes exactly once.
        if target.exists():
            return False
        after.executor().replay(
            operation_id,
            effect=counter.plan(RESOURCE_KEY, RESOURCE_BODY),
            args={"kind": "report"},
        )
        return bool(counter.calls == 1)

    if point.value == "after_write_before_confirm":
        # The bytes are on disk; recovery enters UNCERTAIN and reconciles by
        # probing the world, never by writing again.
        if not target.exists():
            return False
        entered = recovery.mark_uncertain(after.task_id)
        if not entered:
            return False
        outcome = recovery.reconcile(operation_id, expected_sha256=hash_bytes(RESOURCE_BODY))
        if outcome is None:
            return False
        return bool(counter.calls == 1)  # the crash attempt only: no second write

    if point.value == "after_confirm_before_notify":
        # The confirmation committed with the receipt: nothing is uncertain,
        # no replay is possible, and the file was written exactly once — the
        # write the crash itself made, counted by the fresh counter the
        # restart hands back, the way the crash matrix counts it.
        if recovery.mark_uncertain(after.task_id) != ():
            return False
        mtime = target.stat().st_mtime_ns
        replay_counter = after.counter()
        try:
            after.executor().replay(
                operation_id,
                effect=replay_counter.plan(RESOURCE_KEY, RESOURCE_BODY),
                args={"kind": "report"},
            )
            return False
        except Exception:
            return bool(
                replay_counter.calls == 0
                and target.stat().st_mtime_ns == mtime
                and target.read_bytes() == RESOURCE_BODY
            )

    if point.value == "after_attempted_before_write":
        # The intent is durable and the effect did not happen: recovery
        # reconciles the absence and the replay writes exactly once.
        entered = recovery.mark_uncertain(after.task_id)
        if not entered:
            return False
        outcome = recovery.reconcile(operation_id, expected_sha256=hash_bytes(RESOURCE_BODY))
        if outcome is None:
            return False
        after.executor().replay(
            operation_id,
            effect=counter.plan(RESOURCE_KEY, RESOURCE_BODY),
            args={"kind": "report"},
        )
        return bool(counter.calls == 1 and target.exists())

    return False


class _RecoveryEnv:
    """The slice of a ``StoreEnv`` ``build_scenario`` needs, over its own database.

    Recovery's restart disposes the engine it was given, so the crash matrix
    runs on its own database file — the consent workspace's store is never
    the one a restart closes.
    """

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            upgrade_to_head(db_path)
        self.db_path = db_path
        self.engine = create_db_engine(db_path)
        self.factory = create_session_factory(self.engine)
        self.session = self.factory()

    def store(self, *, clock: Any = None) -> Any:
        return TaskStore(self.session) if clock is None else TaskStore(self.session, clock=clock)

    def new_session(self) -> Any:
        return self.factory()

    def dispose(self) -> None:
        self.engine.dispose()


def _sole_operation_id(scenario: Any) -> Any:
    """The one operation the scenario created, or None."""
    from sqlalchemy import select

    from labcairn.db.models import OperationRow

    rows = scenario.env.session.execute(select(OperationRow)).scalars().all()
    return rows[0].operation_id if len(rows) == 1 else None


# --------------------------------------------------------------------------- #
# the run: three faces, one layout, one basis
# --------------------------------------------------------------------------- #


def run(args: argparse.Namespace) -> int:
    """Drive the three faces and write the layout. Returns the exit code."""
    approval = require_live_authorization(Path(args.approval))
    package_dir = Path(args.package)
    validate_package(package_dir)
    manifest_sha = package_manifest_sha256(package_dir)
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise OurSideError(
            f"output directory {out} is not empty; a run's artifacts are written once"
        )
    layout = ArtifactLayout(root=out)
    out.mkdir(parents=True, exist_ok=True)

    context = build_workspace(Path(args.workspace), package_dir)
    call_ceiling = int(args.call_budget)
    calls: list[dict[str, Any]] = []

    def spend(face: str, case: str, **rest: Any) -> None:
        """Count one call against the run's ceiling before it is made."""
        if len(calls) >= call_ceiling:
            raise OurSideError(
                f"the run's call ceiling ({call_ceiling}) is reached; "
                f"{face}/{case} would exceed it — report before spending further"
            )
        calls.append({"face": face, "case": case, **rest})

    # --- the numeric face --------------------------------------------------
    numeric_keys = task_case_files(package_dir, NUMERIC_FACE)
    numeric_fixtures = sorted(
        Path(relpath).name.removesuffix(".expected.json") for relpath in numeric_keys
    )
    selected = numeric_fixtures[: int(args.limit)] if args.limit else numeric_fixtures
    for fixture in selected:
        key = json.loads(
            (
                package_dir / "tasks" / NUMERIC_FACE / "answer-keys" / f"{fixture}.expected.json"
            ).read_bytes()
        )
        material = _numeric_material(package_dir, fixture)
        question = (
            package_dir / "tasks" / NUMERIC_FACE / "questions" / f"{fixture}.question.txt"
        ).read_text(encoding="utf-8")
        prompt = f"{material}\n\n{question}{FORMAT_INSTRUCTION}"
        spend(NUMERIC_FACE, fixture)
        answer_text, call_record = ask_model(
            context,
            Path(args.workspace),
            prompt=prompt,
            material_ref=fixture,
            root_id="source:0",
            purpose="competitor_baseline_numeric_extraction",
        )
        calls[-1].update(call_record)
        cells, refusal_note = score_numeric_case(fixture, key, answer_text)
        _write_artifact(
            layout.answer_path(NUMERIC_FACE, fixture),
            {
                "face": NUMERIC_FACE,
                "case": fixture,
                "scoring": "numeric-cell-exactness",
                "status": "answered",
                "answer": answer_text,
                "cells": cells,
                "refusal_note": refusal_note,
            },
        )

    # --- the abstention face -----------------------------------------------
    if not args.limit:
        for relpath in sorted(task_case_files(package_dir, ABSTENTION_FACE)):
            case = Path(relpath).name.removesuffix(".json")
            material_files = sorted(
                (package_dir / "tasks" / ABSTENTION_FACE / "material").iterdir()
            )
            material = "\n\n".join(path.read_text(encoding="utf-8") for path in material_files)
            question = (
                package_dir / "tasks" / ABSTENTION_FACE / "questions" / f"{case}.question.txt"
            ).read_text(encoding="utf-8")
            prompt = f"{material}\n\n{question}{FORMAT_INSTRUCTION}"
            spend(ABSTENTION_FACE, case)
            answer_text, call_record = ask_model(
                context,
                Path(args.workspace),
                prompt=prompt,
                material_ref=case,
                root_id="source:1",
                purpose="competitor_baseline_unsupported_claim",
            )
            calls[-1].update(call_record)
            _write_artifact(
                layout.answer_path(ABSTENTION_FACE, case),
                {
                    "face": ABSTENTION_FACE,
                    "case": case,
                    "scoring": "abstention-mechanical",
                    "status": "answered",
                    "answer": answer_text,
                },
            )

    # --- the recovery face --------------------------------------------------
    surface_reason = (
        "the product's own executor with transactional recovery; the four "
        "crash windows were executed with the fault armed and the invariant "
        "asserted against the restarted store"
    )
    (out / RECOVERY_FACE).mkdir(parents=True, exist_ok=True)
    (out / RECOVERY_FACE / "surface.json").write_text(
        json.dumps({"surface": "present", "reason": surface_reason}, indent=2, sort_keys=True)
        + "\n"
    )
    outcomes: dict[str, bool] = {}
    if not args.limit:
        from labcairn.recovery.contracts import CrashPoint

        scratch = out / "recovery-scratch"
        for point in CrashPoint:
            # One database per case, the way the crash matrix's own fixtures
            # run: a case's sole-operation read is over a store that holds
            # only that case's operations.
            recovery_env = _RecoveryEnv(Path(args.workspace) / f"recovery-{point.value}.db")
            outcomes[point.value] = run_recovery_case(recovery_env, scratch, point)
        for case, held in sorted(outcomes.items()):
            _write_artifact(
                layout.answer_path(RECOVERY_FACE, case),
                {"face": RECOVERY_FACE, "case": case, "scoring": "recovery-surface", "held": held},
            )

    # --- the side's records -------------------------------------------------
    key_versions = layout.write_key_versions(package_dir)
    case_names = list(numeric_fixtures)
    if not args.limit:
        case_names += [
            Path(relpath).name.removesuffix(".json")
            for relpath in sorted(task_case_files(package_dir, ABSTENTION_FACE))
        ]
        case_names += sorted(outcomes)
    run_document = {
        "label": "labcairn live (LC-P2-18 our side)",
        "package_manifest_sha256": manifest_sha,
        "model": approval.get("model", ""),
        "budget": approval.get("budget", ""),
        "calls": calls,
        "call_count": len(calls),
        "when": datetime.now(UTC).isoformat(),
        "environment": {"os": sys.platform, "python": sys.version.split()[0]},
    }
    layout.run_document_path.write_text(json.dumps(run_document, indent=2, sort_keys=True) + "\n")
    basis = {
        "label": "labcairn live (LC-P2-18 our side)",
        "fixtures": {"names": case_names, "versions": key_versions},
        "model": approval.get("model", ""),
        "budget": approval.get("budget", ""),
        "verified_capabilities": [
            "numeric extraction through the model-call path",
            "abstention behaviour on a no-evidence question",
            "recovery crash matrix executed with armed faults",
        ],
        "limitations": (
            "numeric scoring compares per-(selection, group, statistic) values "
            "with rel_tol=1e-9 and abs_tol=1e-12; a value the model did not "
            "give in parseable shape is a miss, not an omission from the "
            "denominator; a selection the key declares refused produces no "
            "cells — its behaviour is recorded beside them. The model-call "
            "prompts carry this side's output-format instruction, recorded in "
            "the runner, which is a difference in calling protocol from the "
            "competitor side."
        ),
        "confidence_intervals": "none computed — one pass, sixteen task cases",
    }
    layout.basis_document_path.write_text(json.dumps(basis, indent=2, sort_keys=True) + "\n")

    print(f"our side wrote {len(calls)} model calls' artifacts under {out}")
    if args.limit:
        print(f"calibration mode: only the first {len(selected)} numeric fixture(s) ran")
    return 0


def _write_artifact(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LC-P2-18's our-side runner (spends money; gated on approval)."
    )
    parser.add_argument("--package", required=True, help="the task package directory")
    parser.add_argument("--out", required=True, help="output directory for this side's artifacts")
    parser.add_argument(
        "--workspace", required=True, help="workspace directory (store, providers.json)"
    )
    parser.add_argument("--approval", required=True, help="the owner's approval file")
    parser.add_argument(
        "--limit", type=int, default=0, help="calibration: only the first N numeric fixtures"
    )
    parser.add_argument(
        "--call-budget",
        type=int,
        default=16,
        help="the run's own model-call ceiling; a call that would exceed it stops the run",
    )
    args = parser.parse_args()
    try:
        return run(args)
    except LiveRunNotAuthorizedError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    except OurSideError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
