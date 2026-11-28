"""T09 — the isolation half: "without paid APIs" is an assertion here, not a claim.

Three of these are **binding test names** from
``docs/plans/LC-P1-01-task-breakdown.md`` §T09:

* ``test_fake_provider_opens_no_socket``
* ``test_fake_provider_makes_no_outbound_request``
* ``test_fixtures_are_deterministic_by_construction``

The work order discharges *"A FakeProvider and deterministic demo fixtures must
run without paid APIs"* through these. The word that matters is **without**:
nothing here proves the fake is well-behaved, it proves the fake has no way to
behave badly. That is a stronger statement and it is checkable, so this file
takes it.

Two layers, on purpose
---------------------
*Runtime* tests (socket and HTTP patched to raise) demonstrate what actually
happens during a replay. They are the direct answer to "does this make a
network call?"

*Source* tests (AST inspection) prove the capability is absent rather than
merely unused. A runtime test cannot tell "made no request" from "would have
made a request if it had wanted to"; a source test can. Neither layer alone is
sufficient — the runtime test could be satisfied by an unused-but-present import,
and the source test says nothing about what happens at run time. Together they
close the gap, and the source tests are the ones that cannot be skipped.

No test in this file touches the network, so none is marked
``requires_network``. The one test that patches HTTP libraries skips if those
libraries are absent; the socket test is the fallback that never skips.
"""

from __future__ import annotations

import ast
import json
import os
import re
import socket
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from child_encoding import (
    CHILD_OUTPUT_ERRORS,
    PYTHON_OUTPUT_ENCODING,
)
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import ApplicationContext, create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.model_request import ModelInvocation, request_model
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.providers import FakeProvider, ModelProvider, ModelRequest
from labcairn.core.providers.fake import Transcript, TranscriptStep
from labcairn.core.providers.transcripts import ALL_TRANSCRIPTS, USAGE_ABSENT
from labcairn.core.schema import LabCairnModel
from labcairn.db.repository import list_approvals
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.permissions import Grant
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.unit

#: The shared store fixture, bound under the name the signature uses. The
#: end-to-end witness below needs a task to run in; the isolation witnesses
#: above it need nothing but the fake.
env = _shared_env

#: Any import of these would mean the package *could* reach the network.
#: Matched on the root module name so ``import urllib.parse`` is caught too.
_NETWORK_MODULES = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http",
        "httpx",
        "httplib2",
        "requests",
        "smtplib",
        "socket",
        "ssl",
        "telnetlib",
        "urllib",
        "urllib3",
        "xmlrpc",
    }
)

#: Modules that would reintroduce a nondeterministic value.
_NONDETERMINISTIC_MODULES = frozenset({"random", "secrets", "uuid", "time", "os"})

#: Call names that produce a random or process-local value. Low false-positive
#: risk: these are all names nobody invents for a domain operation.
_RANDOMNESS_CALLS = frozenset(
    {
        "urandom",
        "getpid",
        "getenv",
        "environ",
        "uuid1",
        "uuid4",
        "random",
        "randint",
        "randrange",
        "choice",
        "choices",
        "shuffle",
        "sample",
        "token_bytes",
        "token_hex",
    }
)

#: Builtins whose result varies between interpreter runs.
_PROCESS_LOCAL_CALLS = frozenset({"id", "hash"})

#: Wall-clock reads, matched *only* against these stdlib modules so that an
#: unrelated domain method called ``now()`` — ``reading.timestamp.now()`` in
#: LC-P1-08, say — does not fail a gate about determinism. Precision here is
#: deliberate: a lint that cries wolf gets switched off, and a switched-off
#: determinism gate protects nothing.
_CLOCK_MODULES = frozenset({"datetime", "date", "time"})
_CLOCK_CALLS = frozenset(
    {"now", "utcnow", "today", "fromtimestamp", "time", "monotonic", "perf_counter", "process_time"}
)

#: Environment variables that would be a provider credential if any.
_CREDENTIAL_PATTERN = re.compile(
    r"(API_?KEY|SECRET|ACCESS_?KEY|TOKEN|CREDENTIAL|PASSWORD)", re.IGNORECASE
)


def _provider_sources(repo_root: Path) -> list[Path]:
    # core/providers, per ARCHITECTURE.md: core/ owns "config, provider
    # adapters, typed model/tool output".
    return sorted((repo_root / "src" / "labcairn" / "core" / "providers").rglob("*.py"))


def _imported_roots(tree: ast.AST) -> set[str]:
    """Root module name of every import, whether ``import x`` or ``from x import y``."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _calls(tree: ast.AST) -> list[tuple[str, int, str]]:
    """``(callee, lineno, root)`` for every call — the final attribute or name, plus its root.

    ``root`` is the leftmost dotted component (``datetime.now()`` -> ``("now",
    lineno, "datetime")``), so a rule can match ``time.time`` without also
    matching an unrelated ``thing.time``.
    """
    found: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.append((func.id, node.lineno, func.id))
        elif isinstance(func, ast.Attribute):
            target = func.value
            while isinstance(target, ast.Attribute):
                target = target.value
            root = target.id if isinstance(target, ast.Name) else ""
            found.append((func.attr, node.lineno, root))
    return found


# ---------------------------------------------------------------------------
# No network — the hard gate
# ---------------------------------------------------------------------------


def test_provider_modules_import_no_network_library(repo_root: Path) -> None:
    """The package has no network client at all, so it cannot make a request."""
    offenders: list[str] = []
    for path in _provider_sources(repo_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        leaked = _imported_roots(tree) & _NETWORK_MODULES
        if leaked:
            offenders.append(f"{path.name}: imports {sorted(leaked)}")

    assert not offenders, "network imports found in the provider package:\n" + "\n".join(offenders)
    assert _provider_sources(repo_root), "no provider sources found; the sweep proved nothing"


def test_fake_provider_opens_no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """``socket.socket`` and ``create_connection`` raise. A full replay still passes.

    This is the test that cannot be skipped, and it is the direct reading of
    *"without paid APIs"*: the strongest possible HTTP client is disabled and
    the scripted transcripts still run to completion.
    """

    def _forbidden(*args: object, **kwargs: object) -> None:
        msg = "the FakeProvider must never open a socket"
        raise AssertionError(msg)

    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket, "create_server", _forbidden)

    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    for transcript in ALL_TRANSCRIPTS:
        provider = FakeProvider(transcript, clock=lambda: frozen)
        responses = provider.run()
        assert responses, f"{transcript.name} produced nothing"

    # The patch is genuinely in force: constructing a socket now fails, and so
    # does dialling out. If either did not raise, a passing replay above would
    # prove nothing.
    with pytest.raises(AssertionError, match="must never open a socket"):
        socket.socket()
    with pytest.raises(AssertionError, match="must never open a socket"):
        socket.create_connection(("example.invalid", 443))


def test_fake_provider_makes_no_outbound_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every HTTP client constructor raises. A full replay still passes.

    Skipped when the HTTP libraries are absent — in which case the socket test
    above and the source-level import test are still in force. This is the
    belt; the socket test is the braces.
    """
    httpx = pytest.importorskip("httpx")
    requests = pytest.importorskip("requests")

    def _forbidden(*args: object, **kwargs: object) -> None:
        msg = "the FakeProvider must never construct an HTTP client"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx, "Client", _forbidden)
    monkeypatch.setattr(httpx, "AsyncClient", _forbidden)
    monkeypatch.setattr(requests, "get", _forbidden)
    monkeypatch.setattr(requests, "post", _forbidden)
    monkeypatch.setattr(requests.Session, "request", _forbidden)

    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    for transcript in ALL_TRANSCRIPTS:
        assert FakeProvider(transcript, clock=lambda: frozen).run()


def test_fake_provider_does_not_import_the_real_model_layer(repo_root: Path) -> None:
    """``pydantic_ai`` is the paid-model path. The fake must not touch it.

    It is a declared project dependency, so this is a real risk rather than a
    theoretical one: a single convenience import would drag the entire paid
    client stack into a path that must work with no key and no network.

    Checked at the source level rather than by inspecting ``sys.modules``,
    which another test in the same session could have polluted.
    """
    offenders = [
        path.relative_to(repo_root).as_posix()
        for path in _provider_sources(repo_root)
        if "pydantic_ai" in _imported_roots(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert not offenders, f"the fake path imports the paid model layer: {offenders}"

    assert FakeProvider.__module__ == "labcairn.core.providers.fake"


# ---------------------------------------------------------------------------
# No API key
# ---------------------------------------------------------------------------


def test_fake_provider_needs_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every credential-shaped variable from the environment, then replay.

    Includes anything matching the credential pattern, not just a list of names
    somebody thought of — the point is that the run does not consult the
    environment for a key at all, whatever it happens to contain.
    """
    present = [name for name in os.environ if _CREDENTIAL_PATTERN.search(name)]
    for name in present:
        monkeypatch.delenv(name, raising=False)

    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    response = FakeProvider(USAGE_ABSENT, clock=lambda: frozen).run()[0]
    assert response.text

    # And with the names restored by monkeypatch teardown the behaviour is the
    # same, which is the other half of the claim: the presence of a key in the
    # environment does not change what the fake does.
    assert response.usage.input_tokens is not None


def test_fake_provider_needs_no_environment_at_all(repo_root: Path) -> None:
    """A fresh interpreter with a three-variable environment still replays.

    The strongest available statement of "no ambient environment": no ``HOME``,
    no locale, no proxy, no credential, no config file. Combined with the
    byte-identity comparison in the determinism suite, the output is also
    independent of all of them.
    """
    program = (
        "import sys\n"
        "from datetime import UTC, datetime\n"
        "from labcairn.core.providers import FakeProvider\n"
        "from labcairn.core.providers.transcripts import ALL_TRANSCRIPTS\n"
        "frozen = datetime(2026, 1, 1, tzinfo=UTC)\n"
        "for transcript in ALL_TRANSCRIPTS:\n"
        "    assert FakeProvider(transcript, clock=lambda: frozen).run()\n"
        "sys.stdout.write('OK')\n"
    )
    completed = subprocess.run(
        # **``-X utf8``, and not the environment.** Isolated mode (``-I``)
        # ignores ``PYTHONIOENCODING`` and ``PYTHONUTF8``, so the
        # ``PYTHONIOENCODING`` this call sets has no effect at all: the
        # child would write the machine's code page while the parent reads
        # UTF-8, which is the same failure with the arrow turned round.
        # Measured on 2026-11-28 with the project's own CPython 3.12: ``-I``
        # ignores both variables and ``-X utf8`` is what makes the child
        # write UTF-8.
        [sys.executable, "-I", "-X", "utf8", "-c", program],
        capture_output=True,
        text=True,
        encoding=PYTHON_OUTPUT_ENCODING,
        errors=CHILD_OUTPUT_ERRORS,
        cwd=repo_root,
        env={"SYSTEMROOT": "C:\\Windows"},
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, f"replay with no environment failed:\n{completed.stderr}"
    assert completed.stdout == "OK"


# ---------------------------------------------------------------------------
# Determinism by construction
# ---------------------------------------------------------------------------


def test_fixtures_are_deterministic_by_construction(repo_root: Path) -> None:
    """Grep-level assertion: no randomness, no wall clock, no process-local state.

    §T09 requires exactly this, and it is a different guarantee from the
    byte-identity tests: those show *this* fixture set replays identically, this
    one shows *no code path* exists that could break it.
    """
    offenders: list[str] = []
    for path in _provider_sources(repo_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(repo_root)

        for module in sorted(_imported_roots(tree) & _NONDETERMINISTIC_MODULES):
            offenders.append(f"{relative}: imports {module}")

        for callee, lineno, _root in _calls(tree):
            if callee in _RANDOMNESS_CALLS or callee in _PROCESS_LOCAL_CALLS:
                offenders.append(f"{relative}:{lineno}: calls {callee}()")

    assert not offenders, "nondeterminism found in the provider package:\n" + "\n".join(offenders)


def test_provider_package_never_reads_the_clock_directly(repo_root: Path) -> None:
    """``datetime.now()`` is banned outright; a clock arrives only by injection.

    ``ruff``'s ``DTZ`` rules already ban a *naive* ``datetime.now()``. This is
    the stricter rule §5.2 of the task breakdown states — no wall clock at all,
    timezone-aware or not — because ``datetime.now(UTC)`` would pass ``DTZ``
    while still making every replay irreproducible.

    Matched against the stdlib clock modules specifically, so a domain method
    that happens to be called ``now()`` is not caught by a determinism gate.
    """
    offenders: list[str] = []
    for path in _provider_sources(repo_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(repo_root)
        for callee, lineno, root in _calls(tree):
            if root in _CLOCK_MODULES and callee in _CLOCK_CALLS:
                offenders.append(f"{relative}:{lineno}: calls {root}.{callee}()")

    assert not offenders, "wall-clock read found in the provider package:\n" + "\n".join(offenders)


def test_the_clock_gate_would_catch_a_real_clock_read(repo_root: Path) -> None:
    """Guard the guard: the wall-clock rule is shown to fire on a planted read.

    A source-level rule that silently stopped matching would otherwise show as
    a permanently green gate, which is the failure mode T05's exclusions and
    §5.2's grep-level rules are both trying to avoid.
    """
    planted = "from datetime import datetime\n\n\ndef stamp():\n    return datetime.now(UTC)\n"
    hits = [
        (callee, root)
        for callee, _lineno, root in _calls(ast.parse(planted))
        if root in _CLOCK_MODULES and callee in _CLOCK_CALLS
    ]
    assert hits == [("now", "datetime")]

    # …and the precision claim: an unrelated ``.now()`` is not flagged.
    unrelated = "def stamp(reading):\n    return reading.timestamp.now()\n"
    assert not [
        (callee, root)
        for callee, _lineno, root in _calls(ast.parse(unrelated))
        if root in _CLOCK_MODULES and callee in _CLOCK_CALLS
    ]

    # And the sweep really is pointed at real files.
    assert _provider_sources(repo_root), "the clock sweep found no sources; it proved nothing"


# ---------------------------------------------------------------------------
# The seam LC-P1-03 builds on
# ---------------------------------------------------------------------------


def test_fake_provider_satisfies_the_model_provider_protocol(frozen_now: datetime) -> None:
    """Structural conformance, asserted rather than assumed.

    A drift in ``ModelProvider``'s members would otherwise surface as an
    ``AttributeError`` deep inside LC-P1-03's first real adapter, a long way
    from the edit that caused it.
    """
    provider = FakeProvider(USAGE_ABSENT, clock=lambda: frozen_now)

    assert isinstance(provider, ModelProvider)
    assert provider.name == "fake:usage_absent"
    assert provider.send(ModelRequest(prompt="Summarise the attached file.")).text

    # The Protocol declares exactly the two members LC-P1-01 can actually
    # honour. Anything LC-P1-03 adds (capabilities, budget, cancellation) has
    # to be added deliberately rather than discovered as a missing attribute.
    members = {name for name in vars(ModelProvider) if not name.startswith("_")}
    assert members == {"name", "send"}


def test_transcripts_need_no_filesystem_to_resolve(frozen_now: datetime) -> None:
    """A transcript is a value in memory, so no cwd or ``$HOME`` can change it.

    §5.2 lists "no ambient environment" as a determinism rule. This is the
    structural half of it: the fixtures are Python values, so there is no
    directory to locate and no path that could resolve differently on another
    machine or in a wheel install.
    """
    import labcairn.core.providers.transcripts as transcripts_module

    for transcript in ALL_TRANSCRIPTS:
        steps = transcript.steps
        assert steps, f"{transcript.name} has no steps"
        for step in steps:
            assert isinstance(step.wire_json, str)
            assert step.wire_json.startswith("{")
        assert FakeProvider(transcript, clock=lambda: frozen_now).run()

    assert transcripts_module.__file__ is not None


# ---------------------------------------------------------------------------
# The whole path, against the fake, with no network
# ---------------------------------------------------------------------------

#: The destination a permitted request sends to. An example domain.
_DESTINATION = "api.model-provider.example"

#: The material the request is judged against.
_MATERIAL_REF = "proj-1/manuscript.txt"

#: The moment the run is dated.
_MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


class _Card(LabCairnModel):
    """The schema the run asks for: a title and a verdict, both required."""

    title: str
    verdict: str


def _the_transcript() -> Transcript:
    """Two scripted answers, both in the shape the run asked for.

    **Scripted here rather than taken from the shared set** because the
    shared transcripts answer in prose, and a prose answer is not a
    document: this run asks for a schema, so its script has to answer in
    one. The fake's own contract — replay the script, check the request,
    count the exchange — is the same either way.
    """
    return Transcript.of(
        "e2e_task",
        [
            TranscriptStep.of(
                "e2e_task.step1",
                ModelRequest(prompt="What does results.csv contain?"),
                {
                    "text": '{"title": "results.csv", "verdict": "128 rows"}',
                    "tool_calls": [],
                    "usage": {"input_tokens": 40, "output_tokens": 9},
                },
            ),
            TranscriptStep.of(
                "e2e_task.step2",
                ModelRequest(prompt="Summarise it in one sentence."),
                {
                    "text": '{"title": "results.csv", "verdict": "128 rows, 12 columns"}',
                    "tool_calls": [],
                    "usage": {"input_tokens": 55, "output_tokens": 11},
                },
            ),
        ],
    )


def _the_document(answer: str) -> Mapping[str, object] | None:
    """The answer as a document, when it is one — the CLI's own rule."""
    try:
        decoded = json.loads(answer)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _the_invocation(provider: FakeProvider, request: ModelRequest) -> ModelInvocation:
    """One call through the fake, recorded in the layer's wire form.

    **The same wiring the CLI's loop uses** (``labcairn/cli/commands.py``'s
    ``_the_loop_invocation``): the transport's answer is the call's answer,
    the transport's exchange records are carried through unchanged, and the
    document the answer carried is handed to the layer, which judges it
    against the schema it asked for. The fake is the transport here, so
    nothing else is invented.
    """
    before = provider.exchanges()
    answer = provider.send(request)
    after = provider.exchanges()
    fresh = after[len(before) :] if len(after) >= len(before) else after
    return ModelInvocation(
        answer=answer.text,
        provider=provider.name.split(":", 1)[0],
        model=provider.name,
        exchanges=tuple(exchange.to_wire() for exchange in fresh),
        credential_fingerprint="fp-" + "c" * 16,
        structured=_the_document(answer.text),
    )


def _the_context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A store, a task, and a policy that asks — so an approval is needed."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="The fake provider, end to end",
        goal=TaskGoal(
            objective="Ask the fake model under the gates.",
            success_criterion="An answer the consent layer permitted.",
        ),
        source_dirs=(materials,),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _the_use() -> ApprovalUse:
    """What the model call is spent on — the capability whose payload leaves."""
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider="fake",
            model="scripted",
            path=_MATERIAL_REF,
            excerpts=(),
            purpose="guidance_review",
        ).model_dump(),
        root_id="source:0",
        resource_key=_MATERIAL_REF,
    )


def _the_grants() -> list[Grant]:
    """The material-purpose grants the request is judged against."""
    return [
        Grant(
            grant_id="g-model-1",
            subject_ref="proj-1",
            permission="external_transmit",
            purpose="transmit",
            scope="proj-1/**",
            destination=_DESTINATION,
            granted_by="Dr. Chen",
            granted_at=_MOMENT,
            expires_at=None,
            state="active",
            withdrawn_at=None,
            withdrawn_by=None,
            withdrawal_reason=None,
        )
    ]


def _a_granted_approval(context: ApplicationContext) -> ApprovalId:
    """An approval asked for and granted, and not yet spent."""
    asked = request_approval(
        context,
        ApprovalRequest(use=_the_use(), expires_at=_MOMENT.replace(year=2027)),
    )
    approval_id = asked.approval.approval_id
    grant_approval(context, approval_id, now=_MOMENT)
    return approval_id


def _probed(*capable: Capability) -> ProviderCapabilities:
    """A probe record that licenses exactly the capabilities named."""
    outcomes = {
        capability: (
            CapabilityOutcome.OK if capability in capable else CapabilityOutcome.UNSUPPORTED
        )
        for capability in ALL_CAPABILITIES
    }
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp-" + "p" * 16,
        model="scripted",
        protocol="openai-chat",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(
            ALL_CAPABILITIES, "the probe asked and it did not do the thing"
        ),
    )


@pytest.mark.integration
def test_fake_provider_e2e_full_task_without_network(
    env: StoreEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-0002 binding name. The whole path, against the fake, with no network.

    **What the isolation witnesses did not cover.** This file proves the fake
    *has no way* to behave badly: no socket, no HTTP client, no key, no
    environment. What it did not prove is that the path *works* when the fake
    is the model — that a task really does reach the fake, that the answer
    comes back, that the answer is judged against the schema it was asked
    for, and that the exchange lands in the task's log. Six witnesses of a
    capability are not a demonstration of the capability.

    **What "the whole Phase 1 deliverable path" means here.** Phase 1
    promised a provider layer that can be exercised without paid APIs. The
    path is the product's own: a task, an approval asked for and granted, the
    capability gate, the material gate, the call, the answer judged, and the
    exchange written into the task's event log — with the FakeProvider
    behind the seam it was built for. Nothing is stubbed but the model, and
    the model is the fake.

    **And the two capability verdicts.** With a capability set the probe
    licensed, the run happens and the answer decodes. With one the probe
    did not license, the request is refused **before the wire**: the fake is
    never asked, no exchange is recorded, and the approval is still unspent.
    A capability the probe did not confirm is a capability the run does not
    get to try — and the second half of that sentence is the one worth
    checking, because it is the half that costs money.
    """
    from labcairn.db.repository import events_after
    from labcairn.runtime.event import EventType

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the FakeProvider path must never open a socket")

    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket, "create_server", _forbidden)

    context = _the_context(env, tmp_path)
    frozen = datetime(2026, 1, 1, tzinfo=UTC)

    # --- the capability set the probe licensed ----------------------------
    provider = FakeProvider(_the_transcript(), clock=lambda: frozen)
    steps = iter(_the_transcript().steps)

    def _next_invocation() -> ModelInvocation:
        step = next(steps)
        return _the_invocation(provider, step.request)

    for _ in range(2):
        answer = request_model(
            context,
            _a_granted_approval(context),
            _the_grants(),
            use=_the_use(),
            subject_ref="proj-1",
            destination=_DESTINATION,
            material_ref=_MATERIAL_REF,
            at=_MOMENT,
            send=_next_invocation,
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_PROMPTED),
            output_schema=_Card,
        )
        assert answer.answer, "the fake's answer did not reach the caller"
        assert answer.destination == _DESTINATION

    # Both calls are in the task's log, and the log is the only place the
    # call is recorded.
    recorded = [
        event
        for event in events_after(context.store.session, context.task_id)
        if event.type is EventType.MODEL_EXCHANGED
    ]
    assert len(recorded) == 2, f"expected two exchange events; got {recorded!r}"
    assert all(event.payload["provider"] == "fake" for event in recorded)

    # And the fake is the one that was asked, twice.
    assert len(provider.exchanges()) == 2

    # --- the capability set the probe did not license ----------------------
    blocked_provider = FakeProvider(_the_transcript(), clock=lambda: frozen)
    blocked_approval = _a_granted_approval(context)
    reached: list[str] = []

    def _must_not_be_asked() -> ModelInvocation:
        reached.append("the wire was reached")
        step = next(iter(_the_transcript().steps))
        return _the_invocation(blocked_provider, step.request)

    with pytest.raises(ApplicationRefusedError):
        request_model(
            context,
            blocked_approval,
            _the_grants(),
            use=_the_use(),
            subject_ref="proj-1",
            destination=_DESTINATION,
            material_ref=_MATERIAL_REF,
            at=_MOMENT,
            send=_must_not_be_asked,
            capabilities=_probed(),
            output_schema=_Card,
        )

    assert reached == [], "a request the probe did not license reached the wire"
    assert blocked_provider.exchanges() == (), "the fake was asked anyway"
    blocked_recorded = [
        event
        for event in events_after(context.store.session, context.task_id)
        if event.type is EventType.MODEL_EXCHANGED
    ]
    assert len(blocked_recorded) == 2, "a refused request wrote an exchange record"

    # The refused request cost the person nothing: the approval is granted
    # but not spent, while the two that were sent are consumed.
    states = {
        row.approval_id: row.state for row in list_approvals(context.store.session, context.task_id)
    }
    assert states[blocked_approval] != "consumed", (
        f"the refused request spent the approval: {states[blocked_approval]!r}"
    )
    assert sorted(
        state for approval_id, state in states.items() if approval_id != blocked_approval
    ) == ["consumed", "consumed"], f"the two calls that were sent did not spend: {states!r}"
