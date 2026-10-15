"""Stable identity for everything the project records.

Identifiers are UUIDv7. The choice is load-bearing rather than cosmetic:

- **UUIDv7 is time-ordered.** Lexical sort of a v7 UUID matches creation
  order, so indexes stay compact and "roughly insertion order" survives even
  where the authoritative order is ``seq``. It is still *not* the order — see
  ADR-0003 C1 — it is only a property that makes the common case cheap.
- **UUIDv4 would not be.** Random ids scatter across every index page.
- **Monotonic integers would not survive export.** They leak volume and
  collide when two workspaces are merged.

Ids are distinct types rather than bare strings so a ``SourceAnchor`` cannot be
passed where a ``TaskId`` is expected. That is a type error at the boundary
rather than a lookup failure at runtime, and it is the cheapest place to catch.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Annotated, Final

from pydantic import AfterValidator

_UUID_RE: Final = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


_MONOTONIC_LOCK = threading.Lock()
_last_timestamp_ms = 0
_last_counter = 0

#: Bits of sub-millisecond entropy. The UUIDv7 layout gives ``rand_a``
#: exactly **12 bits** (positions 52-63). An earlier draft put a 48-bit
#: counter there, which silently overlapped the timestamp at position 80 and
#: made ordering wrong across millisecond boundaries while still producing
#: UUIDs that *looked* valid. 4096 per millisecond is far beyond any real
#: creation rate here.
_COUNTER_BITS = 12
_COUNTER_MAX = (1 << _COUNTER_BITS) - 1


def new_id() -> uuid.UUID:
    """A fresh UUIDv7.

    ``uuid.uuid7`` arrives in Python 3.14; this project targets 3.12, so the
    construction is spelled out.

    Within a single millisecond the random field is replaced by a **monotonic
    counter**, so two ids minted in the same millisecond still sort in creation
    order. Without it the time-ordered property degrades to "usually", and a
    batch of ids created in one transaction lands scattered across index pages
    in the order that matters most for locality.
    """
    global _last_timestamp_ms, _last_counter

    with _MONOTONIC_LOCK:
        real_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        if real_ms > _last_timestamp_ms:
            _last_timestamp_ms = real_ms
            _last_counter = uuid.uuid4().int & _COUNTER_MAX
        else:
            _last_counter += 1
            if _last_counter > _COUNTER_MAX:
                # Exhausted 4096 ids in one millisecond. Borrow from the next
                # millisecond rather than reseeding the counter: a random value
                # here would reorder ids that share a timestamp, which is the
                # property this function exists to provide.
                _last_timestamp_ms = (_last_timestamp_ms + 1) & 0xFFFFFFFFFFFF
                _last_counter = 0
        # Always emit the *tracked* timestamp, never the raw clock. After a
        # borrow the real clock is behind `_last_timestamp_ms`, and emitting
        # the raw value would step the sequence backwards — which is exactly
        # the bug this comment was written after hitting.
        timestamp_ms = _last_timestamp_ms
        counter = _last_counter

    value = (
        (timestamp_ms << 80)
        | (0x7 << 76)
        | (counter << 64)  # rand_a, 12 bits at positions 64-75
        | (0b10 << 62)  # variant
        | (uuid.uuid4().int & 0x3FFFFFFFFFFFFFFF)  # rand_b
    )
    return uuid.UUID(int=value)


def _validate_uuid7(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        parsed = value
    elif isinstance(value, str):
        if not _UUID_RE.match(value):
            raise ValueError(f"not a UUIDv7: {value!r}")
        parsed = uuid.UUID(value)
    else:
        raise TypeError(f"expected a UUID or UUID string, got {type(value).__name__}")
    if parsed.version != 7:
        raise ValueError(f"expected a UUIDv7 (version 7), got version {parsed.version}")
    return parsed


#: An unvalidated string that must parse as UUIDv7.
type RawId = Annotated[uuid.UUID, AfterValidator(_validate_uuid7)]

# Distinct aliases so the type checker rejects a TaskId used as a RunId.
type TaskId = RawId
type RunId = RawId
type StageId = RawId
type OperationId = RawId
type ApprovalId = RawId
type CheckpointId = RawId
type SourceId = RawId
type EvidenceId = RawId
type ArtifactId = RawId
type EventId = RawId


def is_uuid7(value: object) -> bool:
    """Whether *value* is a UUIDv7 in either UUID or string form."""
    try:
        _validate_uuid7(value)
    except (ValueError, TypeError):
        return False
    return True
