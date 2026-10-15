"""Fakes for the LC-P1-03 provider tests. No socket, no clock, no credential.

The one design decision worth reading
-------------------------------------
:class:`FakeEndpoint` returns pydantic-ai ``ModelResponse`` objects whose
``usage`` is **always the zero default** — ``RequestUsage()``, every counter 0 —
regardless of what raw ``usage`` block the script says was returned.

That is not laziness; it is the trap. It reproduces, exactly, the upstream
failure ADR-0002 §A1 measured::

    tests/test_usage_limits.py:1162  test_usage_unknown_provider
    assert RequestUsage.extract({}, ...) == RequestUsage()

So any adapter or probe that read ``upstream.usage`` would see a plausible,
confidently-wrong ``Known(0)`` for every response in the suite, and every test
below would still pass — for the wrong reason. Instead, the raw ``usage`` block
is written into a :class:`~labcairn.providers.usage_capture.RecordingUsageCapture`
on every call, and a response whose script says ``usage_body=None`` leaves the
capture empty. A test asserting ``Unknown(PROVIDER_OMITTED)`` therefore proves
the raw block was the source, and a test asserting ``Known(12)`` proves it was
read.

Recording every call
--------------------
:attr:`FakeEndpoint.calls` records each request's messages and
``ModelRequestParameters``. That is what makes the negative assertions possible:
"the stage did not start" is asserted as ``len(calls) == 0`` rather than as a
raised exception plus a hope, and "the probe sent no user material" is asserted
by rendering the recorded messages.

No credential exists anywhere in this file, on purpose. The repository forbids
real credentials in tests, and the string that appears in
``test_provider_redaction.py`` is a synthetic, obviously-fake one written for the
scrubbing test.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.usage import RequestUsage

from labcairn.providers.usage_capture import RecordingUsageCapture


def build_upstream_response(
    *,
    text: str = "",
    tool_calls: Sequence[tuple[str, dict[str, Any]]] = (),
    timestamp: datetime,
) -> ModelResponse:
    """A pydantic-ai ``ModelResponse``, always with zero usage.

    See the module docstring for why the usage is zero on purpose.
    """
    parts: list[Any] = []
    if text:
        parts.append(TextPart(content=text))
    for index, (name, args) in enumerate(tool_calls):
        parts.append(ToolCallPart(tool_name=name, args=dict(args), tool_call_id=f"call-{index}"))
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(),
        model_name="fake-endpoint",
        timestamp=timestamp,
    )


@dataclass(frozen=True, slots=True)
class Reply:
    """One scripted reply: what the endpoint says, and what its body contained.

    ``usage_body`` is the **raw** ``usage`` object as an HTTP endpoint would
    return it. ``None`` means the response carried no ``usage`` key at all —
    the row of the contrast table that both upstreams turn into zeros.
    """

    name: str
    text: str = ""
    tool_calls: tuple[tuple[str, dict[str, Any]], ...] = ()
    #: The whole decoded response body, so a test can vary fields other than
    #: ``usage``. Absent entirely when ``None``.
    usage_body: dict[str, object] | None = None
    #: When set, ``request`` raises this instead of replying.
    raises: BaseException | None = None
    #: When true, ``request`` never returns — used only by the timeout test.
    hangs: bool = False


@dataclass(slots=True)
class RecordedCall:
    """One request as the endpoint received it."""

    prompt_text: str
    system_text: str
    tool_names: tuple[str, ...]
    output_mode: str
    allow_text_output: bool
    output_object_schema: dict[str, Any] | None
    prompted_output_template: str | None

    def rendered(self) -> str:
        """Everything the endpoint was told, as one searchable string.

        Built so a test can do ``assert SECRET not in call.rendered()`` rather
        than walking five attributes — the same shape the log assertions use.
        """
        return json.dumps(
            {
                "prompt": self.prompt_text,
                "system": self.system_text,
                "tools": list(self.tool_names),
                "output_mode": self.output_mode,
                "allow_text_output": self.allow_text_output,
                "output_object": self.output_object_schema,
                "prompted_output_template": self.prompted_output_template,
            },
            sort_keys=True,
        )


@dataclass(slots=True)
class FakeEndpoint:
    """An upstream that behaves like a provider without opening a socket.

    Satisfies :class:`~labcairn.providers.adapter.UpstreamModel` and
    :class:`~labcairn.providers.probe.ProbeModel` structurally.
    """

    model_name: str = "fake-model"
    replies: tuple[Reply, ...] = ()
    #: The capture the endpoint writes its raw ``usage`` block into. Shared with
    #: the provider under test, which is exactly how the real sniffer behaves.
    capture: RecordingUsageCapture = field(default_factory=RecordingUsageCapture)
    calls: list[RecordedCall] = field(default_factory=list)
    #: Raised by ``request`` on every call, for "the transport is down" tests.
    always_raises: BaseException | None = None

    @property
    def call_count(self) -> int:
        return len(self.calls)

    async def request(
        self, messages: Any, model_settings: Any, model_request_parameters: Any
    ) -> Any:
        from pydantic_ai.messages import SystemPromptPart, UserPromptPart

        record = RecordedCall(
            prompt_text="".join(
                str(p.content) for p in messages[0].parts if isinstance(p, UserPromptPart)
            ),
            system_text="".join(
                str(p.content) for p in messages[0].parts if isinstance(p, SystemPromptPart)
            ),
            tool_names=tuple(t.name for t in model_request_parameters.function_tools),
            output_mode=str(model_request_parameters.output_mode),
            allow_text_output=bool(model_request_parameters.allow_text_output),
            output_object_schema=(
                dict(model_request_parameters.output_object.json_schema)
                if model_request_parameters.output_object is not None
                else None
            ),
            prompted_output_template=model_request_parameters.prompted_output_template,
        )
        self.calls.append(record)

        if self.always_raises is not None:
            raise self.always_raises

        index = len(self.calls) - 1
        if index >= len(self.replies):
            raise AssertionError(
                f"FakeEndpoint received call {index} but only {len(self.replies)} replies "
                "are scripted; a fake that invents an answer proves nothing"
            )
        reply = self.replies[index]
        if reply.usage_body is not None:
            self.capture.observe({"usage": reply.usage_body})
        if reply.hangs:
            await asyncio.Event().wait()
        if reply.raises is not None:
            raise reply.raises
        return build_upstream_response(
            text=reply.text,
            tool_calls=reply.tool_calls,
            timestamp=_FIXED_TIMESTAMP,
        )


#: One fixed instant for every fake reply, so transcripts are byte-stable.
_FIXED_TIMESTAMP = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


def sync_runner(awaitable: Any) -> Any:
    """Drive a coroutine to completion. The runner injected into tests.

    Separate from the adapter's default so a test never has to reason about
    whether pytest is already inside a loop, and so ``send_from_async_context``
    can assert the *default* runner's diagnosis specifically.
    """
    return asyncio.run(awaitable)
