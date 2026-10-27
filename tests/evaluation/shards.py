"""The CI shards: the required CI tests, read out of the shard file.

**Why this module exists.** The protocol's sixth Phase 1 blocker is about
*"Required CI tests [that] are skipped, ignored or only pass by mocking the
actual behavior under acceptance"*. The harness's three witnesses for it
watch the **mechanism** — the shard list itself, the isolation between
workers, and the rule that reads a witness — rather than the required tests
and what happened to them. So the fact the blocker is about was visible to
nobody: a required test with a skipped case sat in the tree, in the CI
shards on both platforms, and the report said nothing about it. The
blocker's row said HELD, and HELD is a claim.

So the harness reads the shard file. **The shard file is the tree's own
statement of what the CI runs**, so the required tests are read from it
rather than copied into the harness: a copy would drift, and a drifted copy
would name the wrong required tests — which is the same shape of hole the
protocol parser exists to close.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Final

#: The shard file, next to the workflow that uses it.
SHARD_FILE: Final = Path(".github") / "ci-shards.json"


def required_test_files(repo_root: Path) -> tuple[str, ...]:
    """Every test file the CI runs, by bare file name, in name order.

    **Empty when the shard file is not there.** A tree without the shard file
    has no CI to speak of, and saying so with an empty tuple is honest; a
    guess about which files "must" be required would not be.
    """
    path = repo_root / SHARD_FILE
    if not path.is_file():
        return ()
    document = _document(path)
    partitions = document.get("shards")
    if not isinstance(partitions, dict):
        return ()
    names: set[str] = set()
    for shards in partitions.values():
        if not isinstance(shards, list):
            continue
        for shard in shards:
            if not isinstance(shard, list):
                continue
            for entry in shard:
                names.add(PurePosixPath(str(entry)).name)
    return tuple(sorted(names))


def _document(path: Path) -> dict[str, Any]:
    """The shard document, parsed."""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return loaded
