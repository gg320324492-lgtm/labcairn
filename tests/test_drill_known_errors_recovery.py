"""The known-errors drill's recovery half: the abandoned-operation answer.

Drill class 5's recovery arm (work orders §12 §5.1, fifth class), designed at
``docs/plans/LC-P3-07-drill-matrix-design.md`` §2.5 and the backup/rollback
design's §5. The fault is the one a killed process leaves: an operation whose
outcome the record cannot state. The drill proves the product's own answer:

* the recovery pass enters the operation ``UNCERTAIN`` and refuses the next
  run with a message that names the operation **and the one command** that
  answers it — ``labcairn task reconcile <id> --expected-sha256 <hash>``;
* the hash is *not* in the store, so the message says a human must state it;
* a correct ``resolve_abandoned`` answers CONFIRMED when the file carries the
  predicted bytes, and a conflicting hash is a CONFLICT that stays blocked;
* replay is refused for an operation that is not uncertain.

The message-shape assertions are the "known error is expected and named"
claim: the operator can tell which one happened from what the build shows.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import update
from store_support import env as _shared_env

from labcairn.application.recovery import (
    describe_abandoned,
    reconcile_abandoned,
    resolve_abandoned,
)
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.core.ids import OperationId
from labcairn.db.models import OperationRow
from labcairn.runtime.operation import OperationState

env = _shared_env

pytestmark = pytest.mark.integration

EDITED_BYTES = b"drill original line one\ndrill edited line two\ndrill original line three\n"


@pytest.fixture()
def interrupted_rig(env: Any, tmp_path: Any) -> Any:
    """A rig whose publication operation is put back to ``ATTEMPTING``.

    The state a process that died before its confirming transaction leaves —
    the same real drill ``tests/test_revision_loop.py`` runs in-process.
    """
    from drill_support import (
        EDITED_BYTES as DRILL_EDITED,
    )
    from drill_support import (
        MOMENT,
        build_rig,
        grant_copy,
        grant_publication,
    )

    from labcairn.application.revision_loop import publish_revision, stage_copy

    rig = build_rig(env.store(), tmp_path / "workspace")
    stage_copy(rig.context, rig.loop, approval_id=grant_copy(rig), now=MOMENT)
    rig.copy_path().write_bytes(DRILL_EDITED)
    published = publish_revision(
        rig.context,
        rig.loop,
        approval_id=grant_publication(rig),
        edited_bytes=DRILL_EDITED,
        now=MOMENT,
    )
    session = rig.context.store.session
    session.execute(
        update(OperationRow)
        .where(OperationRow.operation_id == str(published.operation.operation_id))
        .values(state=OperationState.ATTEMPTING.value)
    )
    session.commit()
    rig.published = published
    return rig


def test_the_refusal_names_the_operation_and_the_one_command(
    interrupted_rig: Any,
) -> None:
    """A run over an uncertain operation is refused with the remedy stated.

    The message names the operation id, names replay as refused, and prints
    the exact reconcile command — a refusal whose remedy is not stated is a
    dead end rather than a decision.
    """
    abandoned = reconcile_abandoned(interrupted_rig.context)
    assert len(abandoned) == 1
    assert abandoned[0].state is OperationState.UNCERTAIN

    message = describe_abandoned(abandoned)
    assert str(abandoned[0].operation_id) in message
    assert "labcairn task reconcile" in message
    assert "--expected-sha256" in message
    assert "not in the store" in message, (
        "the message says the hash cannot be answered automatically — the "
        "human is the source of the predicted content hash"
    )


def _enter_uncertain(rig: Any) -> Any:
    """The recovery pass, run first: ATTEMPTING becomes UNCERTAIN.

    ``resolve_abandoned`` answers an operation that is *uncertain*; a drill
    that skips this half would be reconciling a state the product never
    holds.
    """
    abandoned = reconcile_abandoned(rig.context)
    assert len(abandoned) == 1
    assert abandoned[0].state is OperationState.UNCERTAIN
    return abandoned[0]


def test_resolve_with_the_predicted_hash_confirms_the_landed_effect(
    interrupted_rig: Any,
) -> None:
    """The probe answers CONFIRMED when the bytes match the stated hash.

    The predicted hash is the publication's own content hash — what a caller
    that planned the write can state and the store cannot reconstruct.
    """
    _enter_uncertain(interrupted_rig)
    outcome = resolve_abandoned(
        interrupted_rig.context,
        OperationId(UUID(str(interrupted_rig.published.operation.operation_id))),
        expected_sha256=interrupted_rig.published.publication_sha256,
    )
    assert outcome.resulting_state is OperationState.CONFIRMED
    assert outcome.verdict.landed is True
    assert outcome.replay_permitted is False


def test_resolve_with_a_wrong_hash_is_a_conflict_that_stays_blocked(
    interrupted_rig: Any,
) -> None:
    """A hash the disk contradicts is a CONFLICT, not a confirmation.

    Overwriting a file this operation did not write is not a recovery — the
    probe refuses and the operation stays blocked for a human.
    """
    _enter_uncertain(interrupted_rig)
    wrong = hashlib.sha256(b"not the bytes on disk").hexdigest()
    with pytest.raises(ApplicationRefusedError) as raised:
        resolve_abandoned(
            interrupted_rig.context,
            OperationId(UUID(str(interrupted_rig.published.operation.operation_id))),
            expected_sha256=wrong,
        )
    assert "conflict" in str(raised.value).lower() or "did not predict" in str(raised.value), (
        f"the conflict is named for a human: {raised.value}"
    )


def test_a_confirmed_operation_is_not_reconciled_again(interrupted_rig: Any) -> None:
    """Replay is refused for an operation that is not uncertain.

    A confirmed operation is settled; reconciling it again would be the
    second-planning the refusal message warns about.
    """
    _enter_uncertain(interrupted_rig)
    resolved = resolve_abandoned(
        interrupted_rig.context,
        OperationId(UUID(str(interrupted_rig.published.operation.operation_id))),
        expected_sha256=interrupted_rig.published.publication_sha256,
    )
    assert resolved.resulting_state is OperationState.CONFIRMED
    with pytest.raises(ApplicationRefusedError) as raised:
        resolve_abandoned(
            interrupted_rig.context,
            OperationId(UUID(str(interrupted_rig.published.operation.operation_id))),
            expected_sha256=interrupted_rig.published.publication_sha256,
        )
    assert "not uncertain" in str(raised.value).lower()
