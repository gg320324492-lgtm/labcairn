"""The witnesses of ``labcairn suggest``: one question about one source.

**What is under test.** The decision the owner took on 2026-11-26: the
product's only CLI route to a model was ``roles run``, which judges
comments and refuses a chain that holds none -- *"a judgement about a
comment that is not there is invented"*. That refusal is the product's own
and it is right there, but it meant that material carrying no comments
could not be put to a model from the command line at all, and the pilot's
round had to go through the Python surface to make its one real request.
``suggest`` is the second route: it reads the material of one source, asks
one question about it, and sends **exactly one** request through the
product's own consent gate.

**The properties, and what would turn each witness red.**

1. **The ask spends nothing.** A call without ``--approval`` writes the
   question down, mints a *pending* approval and returns it. Red if a
   request was sent, if the approval was granted, or if the exchange was
   recorded.
2. **The run sends exactly one request.** Red if the transport was asked
   twice, or not at all.
3. **The transmit check runs before the approval is spent.** A request
   refused for want of a grant leaves the approval **unspent** and sends
   nothing -- a refusal has to cost the person nothing.
4. **No key is ever printed or written.** Red if the credential's value
   reaches the output, the file the answer was written to, or the store.
5. **The refusals use the product's own vocabulary.** Each refusal the
   command owns has a witness of its own.
6. **The answer is written into the workspace.** Red if the file is not
   there, or if its bytes are not the ones the outcome names.
7. **It is not the advisor loop.** It asks a question; it judges no
   comment, and it refuses nothing because the chain holds no comment.

**The transport is stubbed at the seam the wiring reads it through**, so
the command runs in this process. The real transport would want a network
and a paid call, and what is under test here is the command's use of the
gate -- how many requests it makes, in what order, and what it writes --
not the provider's reach. The seams are the same ones
``tests/test_service_model_wiring.py`` drives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from test_cli_support import (
    _context,
    run_cli,
)
from test_cli_support import (
    task_id as _task_id_fixture,
)
from test_cli_support import (
    workspace as _workspace_fixture,
)
from typer.testing import CliRunner

from labcairn.cli.commands import EXIT_REFUSED, app
from labcairn.core.providers.protocol import ModelRequest
from labcairn.core.providers.usage import Known
from labcairn.db.repository import list_approvals
from labcairn.providers.adapter import ExchangeRecord, OutboundDisclosure, prompt_digest
from labcairn.providers.capabilities import ProviderCapabilities
from labcairn.runtime.operation import ApprovalState

workspace = _workspace_fixture
task_id = _task_id_fixture

pytestmark = pytest.mark.e2e


# --------------------------------------------------------------------------- #
# the workspace the witnesses run on
# --------------------------------------------------------------------------- #

#: The provider the authorisation record names.
PROVIDER = "pilot-provider"

#: The destination the record names. The grant covers this destination and
#: no other, so a request addressed elsewhere is refused by the gate.
DESTINATION = "api.pilot-provider.example"

#: The subject the record names, and the project the material belongs to.
SUBJECT_REF = "proj-suggest"

#: The credential variable the provider entry names. Set for the witnesses
#: that wire a provider; deliberately unset everywhere else.
CREDENTIAL_ENV = "LABCAIRN_SUGGEST_TEST_ONLY_KEY"

#: A synthetic key. The repository forbids real credentials in tests, and
#: this one is obviously fake: it exists so that a witness can look for it
#: and find nothing.
FAKE_KEY = "sk-suggest-not-a-real-key-0123456789"

#: The material the witnesses ask about, and where it lives under the
#: source root. **The path matters**: the grant's scope is the subject's
#: path, so the material has to be under it or the transmit gate refuses.
MATERIAL_RELATIVE = "proj-suggest/notes.txt"

#: The material's own words. Short, so that a witness can quote them.
MATERIAL_TEXT = "The pilot round read one copy of the paper and wrote a report about it.\n"

#: The question the witnesses ask.
QUESTION = "What does the material say the round established?"

#: The answer the stubbed transport gives. Fixed words, so that a witness
#: can compare them.
ANSWER = "The material says that the round read one copy and wrote a report."

#: The moment the stubbed transport's exchange records carry. Fixed, so
#: that a record does not depend on when the witness ran.
OBSERVED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _providers_file(*, scope: str = f"{SUBJECT_REF}/**") -> str:
    """The workspace's provider configuration, with the owner's record in it.

    **The record is the grant.** It names the provider, the destination and
    the subject, and the transmit gate checks the request against it -- so
    a request is permitted only because this file says it may be. The
    credential itself is not here: it stays in the environment, under the
    variable the provider entry names.
    """
    document = {
        "providers": {
            PROVIDER: {
                "protocol": "openai_compatible",
                "model": "pilot-model",
                "base_url": "http://127.0.0.1:9/v1",
                "credential_env": CREDENTIAL_ENV,
            },
        },
        "model_suggestions": {
            "provider": PROVIDER,
            "destination": DESTINATION,
            "subject_ref": SUBJECT_REF,
            "scope": scope,
            "granted_by": "owner",
            "granted_at": "2026-11-24T00:00:00+00:00",
        },
    }
    return json.dumps(document, indent=2, sort_keys=True)


@dataclass
class _RecordingTransport:
    """A transport that records what it was asked and answers with fixed words.

    **No network, no credential and no provider.** The seam the CLI's wiring
    reads is the transport's own members, so a stub that satisfies it is
    what the wiring can be exercised with. What is under test is the
    command's use of the gate, not the provider's reach -- and the record
    of what the transport was asked is what makes "exactly one request" a
    fact rather than an inference.
    """

    answer: str = ANSWER
    prompts: list[str] = field(default_factory=list)
    model_id: str = f"{PROVIDER}:pilot-model"
    records: list[ExchangeRecord] = field(default_factory=list)

    def send(self, request: ModelRequest) -> str:
        """One request out, one answer back.

        **The exchange is recorded, because the store's record of the call
        needs one.** The record is the provider layer's own wire form --
        digests and counts, never text -- so what the event log holds about
        this call is the same shape a real call's would be.
        """
        self.prompts.append(request.prompt)
        self.records.append(
            ExchangeRecord(
                provider=PROVIDER,
                model=self.model_id,
                transcript_step="the-answer",
                prompt_digest=prompt_digest(request.prompt),
                tool_names=(),
                outbound=OutboundDisclosure(),
                provider_attempts=1,
                observed_at=OBSERVED_AT,
                usage_input=Known(0),
                usage_output=Known(0),
            )
        )
        return self.answer

    @property
    def credential_fingerprint(self) -> str:
        """Which credential the exchange was recorded under, and no value."""
        return "fp-" + "0" * 16

    @property
    def capabilities(self) -> ProviderCapabilities | None:
        """No probe has run, and this request asks for no schema."""
        return None

    def exchanges(self) -> tuple[ExchangeRecord, ...]:
        """The provider layer's own record of the calls it has made."""
        return tuple(self.records)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> _RecordingTransport:
    """The transport the command reaches, replaced by the recorder.

    **Replaced where the wiring reads it.** The real transport would want a
    network and a paid call. The property under test is what the command
    does with the consent gate, so the transport is replaced and every
    request it was asked to make is recorded.
    """
    from labcairn.cli import commands

    recorder = _RecordingTransport()
    monkeypatch.setattr(commands, "_suggestion_transport", _the_recorder(recorder))
    return recorder


def _the_recorder(recorder: _RecordingTransport) -> Any:
    """The stub the wiring reaches, bound to the recorder it records into."""

    def _stub(settings: Any, credential: Any, probe_cache: Any = None) -> _RecordingTransport:
        return recorder

    return _stub


@pytest.fixture
def authorised(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner's authorisation, as the workspace records it.

    **The record is the grant, and the grant is the only thing that lets
    the material go.** A workspace without this file names no provider and
    no destination, and the command refuses rather than guessing.
    """
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    (workspace / "providers.json").write_text(_providers_file(), encoding="utf-8")


@pytest.fixture
def source(workspace: Path, task_id: str) -> str:
    """A material in the ledger, ingested by the product's own ingestion.

    **Ingested, not written.** A source the ledger holds but that carries
    no text is a source with no material to ask about, and the question
    this command asks is about the material. The product's own
    ``sources ingest`` is what puts both the row and the text there, and it
    binds the source to the task -- which is what lets the command read it
    at all.
    """
    path = workspace / "materials" / MATERIAL_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MATERIAL_TEXT, encoding="utf-8")
    result = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert result.returncode == 0, result.stderr
    return str(result.json()["source_ids"][0])


# --------------------------------------------------------------------------- #
# running the command
# --------------------------------------------------------------------------- #


def _run(workspace: Path, *args: str) -> Result:
    """The CLI, in this process, with the arguments a person would type.

    **The width is declared.** Rich asks the terminal how wide it is, and a
    captured stream is not a terminal, so the width would be eighty columns
    and a long path would be wrapped in the middle. The width of a terminal
    is a property of the terminal, and a witness that asserted on a wrapped
    path would be asserting on the machine rather than on the CLI.
    """
    return CliRunner().invoke(app, ["--workspace", str(workspace), *args], env={"COLUMNS": "200"})


def _ask(workspace: Path, source_id: str) -> dict[str, Any]:
    """The command's ask: the question, and the approval to grant."""
    result = _run(
        workspace,
        "suggest",
        "--source",
        source_id,
        "--question",
        QUESTION,
        "--json",
    )
    assert result.exit_code == 0, result.output
    return dict(json.loads(result.stdout))


def _grant(workspace: Path, approval_id: str) -> None:
    """A person's yes, through the command that records it."""
    result = run_cli("--workspace", str(workspace), "task", "approval-grant", approval_id)
    assert result.returncode == 0, result.stderr


def _run_with_approval(workspace: Path, source_id: str, approval_id: str) -> Result:
    """The command's run: the same question, spent against the approval."""
    return _run(
        workspace,
        "suggest",
        "--source",
        source_id,
        "--question",
        QUESTION,
        "--approval",
        approval_id,
        "--json",
    )


def _the_approval_states(workspace: Path, task: str) -> list[ApprovalState]:
    """The approvals the ledger holds for the task, and their states."""
    with _context(workspace, task) as context:
        approvals = list_approvals(context.store.session, context.task_id)
    return [approval.state for approval in approvals]


# --------------------------------------------------------------------------- #
# 1. the ask spends nothing
# --------------------------------------------------------------------------- #


def test_the_ask_writes_the_question_down_and_spends_nothing(
    workspace: Path, task_id: str, source: str, authorised: None, transport: _RecordingTransport
) -> None:
    """The ask is a question and a pending approval, and nothing else.

    **What would turn this red.** A request sent during the ask, an
    approval that was already granted, or an exchange recorded. The
    transport records what it was asked, so "nothing was sent" is a fact
    about the calls rather than an inference from the absence of an error,
    and the ledger's own state says whether the approval is pending.

    **And the approval is a question, not a blank cheque.** It carries the
    digest of the question and of the material, so the grant that follows
    it is a grant for *this* question about *this* material.
    """
    asked = _ask(workspace, source)

    assert asked["approval_id"]
    assert asked["question"] == QUESTION
    assert asked["source_id"] == source
    assert transport.prompts == []
    assert _the_approval_states(workspace, task_id) == [ApprovalState.PENDING]


def test_the_ask_names_the_material_it_would_send(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """The ask says what would leave, and by how much of it.

    **What would turn this red.** An ask that named no material, or one
    that did not say how much of the material the question was about. A
    person who grants an approval for a question about a document has to
    know which document, and how much of it -- a reader who was not told
    the excerpt was cut would read the answer as an answer about the whole.
    """
    asked = _ask(workspace, source)

    assert asked["material_sha256"]
    assert asked["material_characters"] == len(MATERIAL_TEXT.strip())
    assert asked["excerpt_characters"] == asked["material_characters"]
    assert asked["truncated"] is False
    assert asked["provider"] == PROVIDER
    assert asked["destination"] == DESTINATION


# --------------------------------------------------------------------------- #
# 2. the run sends exactly one request
# --------------------------------------------------------------------------- #


def test_the_run_sends_exactly_one_request(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """One approval, one request, one answer.

    **What would turn this red.** The transport asked twice -- the command
    asking twice is the failure the count exists to catch -- or asked not
    at all, which would make the answer a fabrication. The count is read
    from the transport's own record, and the approval's own state says the
    one request was paid for.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    result = _run_with_approval(workspace, source, asked["approval_id"])

    assert result.exit_code == 0, result.output
    outcome = json.loads(result.stdout)
    assert outcome["answer"] == ANSWER
    assert len(transport.prompts) == 1
    assert _the_approval_states(workspace, task_id) == [ApprovalState.CONSUMED]


def test_the_request_carries_the_material_and_the_question(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """What left the machine is the question and the material, and nothing else.

    **What would turn this red.** A prompt that carried no material, or
    that carried a different question from the one that was asked for. The
    transport records the prompt it was handed, so both are read out of the
    request itself rather than out of the command's own account of it.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    _run_with_approval(workspace, source, asked["approval_id"])

    assert len(transport.prompts) == 1
    prompt = transport.prompts[0]
    assert QUESTION in prompt
    assert MATERIAL_TEXT.strip() in prompt


# --------------------------------------------------------------------------- #
# 3. the transmit check runs before the approval is spent
# --------------------------------------------------------------------------- #


def test_a_refused_transmit_leaves_the_approval_unspent(
    workspace: Path,
    task_id: str,
    source: str,
    monkeypatch: pytest.MonkeyPatch,
    transport: _RecordingTransport,
) -> None:
    """A request the grant does not cover costs the person nothing.

    **What would turn this red.** The approval **consumed** and nothing
    sent -- the person would have to ask again for a grant they had
    already given, every time the grant was missing. Asking is not
    spending, and this is where that is true.

    **The grant here does not reach the material.** The authorisation
    record's scope names a path the material is not under, so the transmit
    gate refuses the request -- and the refusal is the layer's own
    vocabulary, not a string this command invented.
    """
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    (workspace / "providers.json").write_text(
        _providers_file(scope="somewhere-else/**"), encoding="utf-8"
    )
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    result = _run_with_approval(workspace, source, asked["approval_id"])

    assert result.exit_code == EXIT_REFUSED, result.output
    refusal = json.loads(result.stdout)
    assert refusal["reason"] == "consent_scope_not_covered"
    assert transport.prompts == []
    assert _the_approval_states(workspace, task_id) == [ApprovalState.GRANTED]


def test_the_approval_is_spent_only_by_a_request_that_went_out(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """What the approval bought is the request, and the request is one.

    **What would turn this red.** An approval consumed while the transport
    was never asked -- the consent spent on nothing -- or an approval left
    granted while a request went out. The two facts are read from the two
    places that hold them: the ledger's state and the transport's record.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])
    assert _the_approval_states(workspace, task_id) == [ApprovalState.GRANTED]

    _run_with_approval(workspace, source, asked["approval_id"])

    assert len(transport.prompts) == 1
    assert _the_approval_states(workspace, task_id) == [ApprovalState.CONSUMED]


# --------------------------------------------------------------------------- #
# 4. no key is ever printed or written
# --------------------------------------------------------------------------- #


def test_no_key_is_ever_printed_or_written(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """The credential's value reaches neither the output nor the workspace.

    **What would turn this red.** The key appearing in the command's
    output, in the file the answer was written to, or in the store. The
    call is recorded under a fingerprint, and the exchange records carry
    digests and counts -- so there is no field anywhere a key could
    occupy, and this witness reads the whole database to say so rather
    than trusting the shape of the schema.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    result = _run_with_approval(workspace, source, asked["approval_id"])

    assert result.exit_code == 0, result.output
    outcome = json.loads(result.stdout)
    written = (workspace / outcome["answer_path"]).read_text(encoding="utf-8")
    assert FAKE_KEY not in result.stdout
    assert FAKE_KEY not in result.stderr
    assert FAKE_KEY not in written
    assert FAKE_KEY.encode("utf-8") not in (workspace / "labcairn.db").read_bytes()


# --------------------------------------------------------------------------- #
# 5. the refusals use the product's own vocabulary
# --------------------------------------------------------------------------- #


def test_an_empty_question_is_refused_by_the_cli(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """A question with no words is refused, and it costs nothing.

    **What would turn this red.** The command accepting an empty question
    and asking it -- a request that carries no question would spend an
    approval on silence -- or refusing it with a reason of its own making
    instead of the CLI's own vocabulary.
    """
    result = _run(workspace, "suggest", "--source", source, "--question", "   ", "--json")

    assert result.exit_code == EXIT_REFUSED, result.output
    refusal = json.loads(result.stdout)
    assert refusal["reason"] == "invalid_arguments"
    assert "the question is empty" in refusal["message"]
    assert transport.prompts == []


def test_a_workspace_that_names_no_provider_is_refused(
    workspace: Path, task_id: str, source: str, transport: _RecordingTransport
) -> None:
    """No provider, no destination, no request.

    **What would turn this red.** The command inventing a provider or a
    destination to ask -- a request that left the machine without the
    owner's record saying where it may go would be the one thing this
    product is not allowed to do -- or refusing with a reason outside the
    product's own vocabulary.
    """
    result = _run(workspace, "suggest", "--source", source, "--question", QUESTION, "--json")

    assert result.exit_code == EXIT_REFUSED, result.output
    refusal = json.loads(result.stdout)
    assert refusal["reason"] == "no_provider"
    assert "the workspace names no provider to ask" in refusal["message"]
    assert transport.prompts == []


def test_a_source_the_ledger_does_not_hold_is_refused(
    workspace: Path,
    task_id: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """A source that is not there is the layer's refusal, not the CLI's.

    **What would turn this red.** The command answering about a source the
    ledger does not hold -- or refusing it in a vocabulary of its own
    instead of the layer's.
    """
    result = _run(
        workspace,
        "suggest",
        "--source",
        "src-does-not-exist",
        "--question",
        QUESTION,
        "--json",
    )

    assert result.exit_code == EXIT_REFUSED, result.output
    refusal = json.loads(result.stdout)
    assert refusal["reason"] == "source_not_found"
    assert transport.prompts == []


def test_an_approval_that_covers_another_question_is_refused(
    workspace: Path, task_id: str, source: str, authorised: None, transport: _RecordingTransport
) -> None:
    """An approval granted for one question does not authorise another.

    **What would turn this red.** The run spending an approval whose
    digest covers a different question -- which would make the consent
    bind nothing at all, since a person could grant one thing and the
    command would spend it on another.

    **The question is different; the material is the same.** So the
    approval's own digest is what differs, and the spend is refused
    because the approval does not cover this question.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    result = _run(
        workspace,
        "suggest",
        "--source",
        source,
        "--question",
        "A different question entirely?",
        "--approval",
        asked["approval_id"],
        "--json",
    )

    assert result.exit_code == EXIT_REFUSED, result.output
    refusal = json.loads(result.stdout)
    assert refusal["reason"] == "approval_refused"
    assert transport.prompts == []
    assert _the_approval_states(workspace, task_id) == [ApprovalState.GRANTED]


# --------------------------------------------------------------------------- #
# 6. the answer is written into the workspace
# --------------------------------------------------------------------------- #


def test_the_answer_is_written_into_the_workspace(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """What came back is on disk, in the workspace, and checkable.

    **What would turn this red.** The answer printed and nowhere else --
    so that the next person to ask the same question would have to pay for
    it again -- or a file whose bytes are not the ones the outcome names.

    **The file names the question it answers.** A file that carried only
    an answer would not say what it was an answer to.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    result = _run_with_approval(workspace, source, asked["approval_id"])

    assert result.exit_code == 0, result.output
    outcome = json.loads(result.stdout)
    path = workspace / outcome["answer_path"]
    assert path.is_file()
    written = path.read_text(encoding="utf-8")
    assert ANSWER in written
    assert QUESTION in written
    assert path.stat().st_size == outcome["answer_bytes"]


# --------------------------------------------------------------------------- #
# 7. it is not the advisor loop
# --------------------------------------------------------------------------- #


def test_a_source_with_no_comments_is_not_refused(
    workspace: Path,
    task_id: str,
    source: str,
    authorised: None,
    transport: _RecordingTransport,
) -> None:
    """Material carrying no comments can still be put to a model.

    **What would turn this red.** The command refusing with the advisor
    loop's own reason -- *``role_comment_not_in_the_chain``* -- which is
    right for a loop that judges comments and wrong for a command that
    asks a question. The workspace in this file holds a material and no
    comment at all, so the refusal would be the only outcome available if
    the command were the loop.
    """
    asked = _ask(workspace, source)
    _grant(workspace, asked["approval_id"])

    result = _run_with_approval(workspace, source, asked["approval_id"])

    assert result.exit_code == 0, result.output
    outcome = json.loads(result.stdout)
    assert outcome["answer"] == ANSWER
    assert "role_comment_not_in_the_chain" not in result.stdout
    assert "role_comment_not_in_the_chain" not in result.stderr
