"""The task store: SQLite as the application-owned authority for Task state.

Phase 1 of LC-P1-05. What this package is responsible for:

* the eight tables (task, run, stage, event, operation, approval, checkpoint,
  artifact) and the migrations that create them,
* a per-Task gapless event sequence that is **not** the rowid,
* the transaction boundary that couples events to the state rows they describe,
* stable Task identity across a restart.

What it deliberately is not: a crash-recovery mechanism. Reconciling an
interrupted side effect, resuming from a checkpoint and deciding whether a model
call happened are LC-P1-06, and the pieces it needs — ``checkpoints``,
``operation_uncertain``, ``through_seq`` — are present here as storage but no
logic reads them back yet.
"""

from __future__ import annotations

from labcairn.db.base import Base
from labcairn.db.models import (
    LOCAL_USER_ID,
    ApprovalRow,
    ArtifactRow,
    CheckpointRow,
    EventRow,
    OperationRow,
    RunRow,
    StageRow,
    TaskRow,
)
from labcairn.db.repository import (
    StoredApprovalLedger,
    StoreError,
    TaskStore,
    UnitOfWork,
    UnknownTaskError,
    count_events,
    events_after,
    last_seq,
    select_events,
)
from labcairn.db.session import (
    create_db_engine,
    create_session_factory,
    session_scope,
)

__all__ = [
    "LOCAL_USER_ID",
    "ApprovalRow",
    "ArtifactRow",
    "Base",
    "CheckpointRow",
    "EventRow",
    "OperationRow",
    "RunRow",
    "StageRow",
    "StoreError",
    "StoredApprovalLedger",
    "TaskRow",
    "TaskStore",
    "UnitOfWork",
    "UnknownTaskError",
    "count_events",
    "create_db_engine",
    "create_session_factory",
    "events_after",
    "last_seq",
    "select_events",
    "session_scope",
]
