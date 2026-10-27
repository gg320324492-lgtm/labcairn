"""The two capability vocabularies must stay disjoint — ADR-0006.

LC-P1-03 and LC-P1-04 were built by two agents that never read each other's
work, and they each invented a capability namespace. The namespaces happen not
to overlap, which is the correct outcome and not an accident to be tidied away:
one names facts about a model, the other names grants to this process.

These tests make that a property rather than a coincidence. A merge fails the
first test instead of being discovered during a security review.

The third test deliberately asserts a **limitation**: today the provider layer
does not consult the permission layer at all. That is expected to break when
the LC-P1-05 bridge lands, and that is the point — the bridge should be a
visible edit, not drift nobody notices.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from labcairn.providers.capabilities import Capability as ProviderCapability
from labcairn.security.capabilities import CapabilityId

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src" / "labcairn"


def _provider_values() -> set[str]:
    return {m.value for m in ProviderCapability}


def _permission_values() -> set[str]:
    return {
        str(getattr(CapabilityId, name)) for name in dir(CapabilityId) if not name.startswith("_")
    }


def test_the_two_capability_namespaces_are_disjoint() -> None:
    """A capability of a model is not a grant to this process.

    ``tool_calls`` says the model will emit tool calls; ``fs.write`` says this
    process may write. Merging them would let one side's answer stand in for
    the other's, which is how a model that can call tools comes to authorise a
    write it should not have.
    """
    overlap = _provider_values() & _permission_values()
    assert not overlap, (
        f"{sorted(overlap)} appear in both vocabularies. A model capability and a "
        f"permission capability answer different questions and must not be merged; "
        f"see ADR-0006."
    )


def test_outbound_has_a_permission_capability() -> None:
    """Sending anything to a provider is itself an outbound action.

    Without this, "gate the outbound path" would have nothing to gate on, and
    the phrase would be a sentiment rather than a design.
    """
    assert "model.request" in _permission_values(), (
        "ADR-0006 gates outbound transmission on MODEL_REQUEST; without it the "
        "decision has nothing to gate on."
    )
    assert str(CapabilityId.MODEL_REQUEST) == "model.request"


def _imports_security() -> bool:
    for path in (SRC / "providers").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("labcairn.security")
            ) or (
                isinstance(node, ast.Import)
                and any(a.name.startswith("labcairn.security") for a in node.names)
            ):
                return True
    return False


def test_providers_does_not_import_the_permission_layer() -> None:
    """Pins a known limitation rather than pretending it is solved.

    ADR-0006 decides that an outbound transmission is ``MODEL_REQUEST`` and
    must be gated. That coupling is **not yet enforced**: a caller can still
    reach ``provider.send()`` without a permission decision.

    When the LC-P1-05 bridge lands, this test is expected to fail. That failure
    is correct — it should be a visible change to a decision, not a silent one.
    """
    assert not _imports_security(), (
        "providers/ now imports the permission layer. If this is the LC-P1-05 "
        "outbound-consent bridge landing, update ADR-0006 and move this test to "
        "assert the bridge exists rather than that it is absent."
    )
