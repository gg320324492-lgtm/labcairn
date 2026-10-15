"""Schema versioning, and what happens when a stored payload no longer fits.

Every persisted contract carries ``schema_version``. Two rules make it useful
rather than decorative:

1. **A payload from a newer version is refused, never guessed at.** A reader
   that does not know field 4 exists cannot know what field 4 means, and
   silently dropping it is how provenance gets lost without anyone noticing.
2. **A payload from an older version may be migrated, and the migration is
   explicit.** Refusing every historical payload would make the store
   unreadable after the first release, which is the same failure in the other
   direction.

The registry is the single place that knows which versions exist. Adding a
version means adding an entry here and a migration; nothing else in the
codebase branches on a version number.
"""

from __future__ import annotations

import json
from typing import Final

from pydantic import BaseModel, ConfigDict

#: The version every contract currently writes.
CURRENT_SCHEMA_VERSION: Final = 1

#: The lowest version this build can still read. Anything older is refused
#: rather than migrated, because no migration exists for it — see
#: :class:`SchemaVersionError`.
MINIMUM_READABLE_SCHEMA_VERSION: Final = 1


class SchemaVersionError(ValueError):
    """A payload's ``schema_version`` is outside what this build can handle.

    Distinct from a normal validation error on purpose: the remedy is different.
    A malformed field means the caller sent bad data; an unsupported version
    means the caller is *newer or older than this build*, and retrying will
    not help.
    """

    def __init__(self, *, found: int, minimum: int, current: int, contract: str) -> None:
        direction = "newer than" if found > current else "older than"
        super().__init__(
            f"{contract}: schema_version {found} is {direction} this build "
            f"(reads {minimum} to {current})"
        )
        self.found = found
        self.minimum = minimum
        self.current = current
        self.contract = contract


class LabCairnModel(BaseModel):
    """Base for every persisted contract.

    ``extra="forbid"`` is the important setting. A payload carrying a field
    this build does not know is **rejected**, not ignored: an unrecognised key
    is either a newer writer or a typo, and both deserve to be loud. The
    forward-compatibility cost is real and is paid deliberately — see
    :class:`SchemaVersionError`.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        # NaN/Inf are rejected rather than serialised. JSON has no literal for
        # either, so allowing them here would produce bytes that another
        # reader cannot round-trip — a silent corruption at the boundary.
        # `allow_inf_nan=False` is the pydantic spelling that both rejects them
        # on input and refuses to emit them.
        allow_inf_nan=False,
    )

    schema_version: int = CURRENT_SCHEMA_VERSION

    def check_version(self, *, contract: str | None = None) -> None:
        """Raise if this payload's version is outside the readable range."""
        found = self.schema_version
        if not (MINIMUM_READABLE_SCHEMA_VERSION <= found <= CURRENT_SCHEMA_VERSION):
            raise SchemaVersionError(
                found=found,
                minimum=MINIMUM_READABLE_SCHEMA_VERSION,
                current=CURRENT_SCHEMA_VERSION,
                contract=contract or type(self).__name__,
            )

    def json_canonical(self) -> str:
        """Deterministic JSON: sorted keys, no incidental whitespace.

        Used wherever bytes must be stable — an approval's argument digest, a
        content hash, a byte-identity comparison between platforms. Ordinary
        :meth:`pydantic.BaseModel.model_dump_json` is used for storage, where
        key order does not matter.
        """
        return json.dumps(
            json.loads(self.model_dump_json()),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
