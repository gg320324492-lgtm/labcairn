"""The corpus in the tree, and the manifest that names it.

**What this file watches.** LC-P2-10's T02 shipped two things that belong
to each other: the synthetic manuscripts the annotations are read against,
and the manifest that names them. **A manifest and a corpus drift apart
quietly** — one is regenerated and the other is not, and every witness
that reads the manifest alone stays green while the gold set starts
pointing at comments that are no longer there.

So the checks here are **about the pair**, not about either half:

- the manifest in the tree parses under the contract the tree ships;
- every item names a comment the corpus has, with the id the id rules
  give it, and the corpus section records the hash of the bytes that
  are actually written;
- the corpus is **reproducible** — the same manuscripts every time, so a
  reviewer can regenerate what the manifest describes;
- the feedback ids are the chain's own, so the manifest's rows can be
  joined to the chain's events;
- **the annotations are all or nothing** — a manifest with one reading on
  one item and two on the next is a manifest mid-flight, and it is
  indistinguishable from a finished one to a reader who does not look;
- and the completion check agrees with the manifest's own state, so it
  never passes a half-annotated set and never refuses a finished one.

**These witnesses do the checking themselves.** The corpus module carries
three self-checks of its own, and calling one of them from a test would
be **delegating the property to the code under test**: empty that
function out and the test still passes, because the test asked the thing
that was broken. So every property here is checked in this file, against
the module's *materials* — the fixtures it writes and the ids it derives
— and never by asking it whether it is satisfied.

**The last two witnesses are written to hold either way.** The annotations
were nobody's work when this file was written — that was T06, and §6 of the
acceptance record said so — so the manifest in the tree shipped with empty
`annotations` blocks. **These witnesses do not insist on that emptiness:
they insist that whatever state the manifest is in, it is a state the
completion check reads correctly.** When the two annotators and the arbiter
have done their work, the same witnesses hold — and they do now.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest
from gold_set_fixtures import feedback_id, gold_fixtures, item_id, write_corpus

from labcairn.papers.gold_manifest import (
    MANIFEST_RELATIVE_PATH,
    load_manifest,
    require_annotated,
    validate_manifest,
)

pytestmark = pytest.mark.unit

#: The manifest in the tree.
MANIFEST: Path = MANIFEST_RELATIVE_PATH

#: The moment a ZIP archive can express that is obviously a constant: the
#: earliest one the format has.
_ZIP_EPOCH: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)


def _document() -> dict[str, Any]:
    """The manifest in the tree, read as the raw document it is."""
    return cast(dict[str, Any], json.loads(MANIFEST.read_text(encoding="utf-8")))


def _comments_in_the_corpus() -> set[tuple[str, str]]:
    """Every (fixture, comment) the corpus holds."""
    return {
        (fixture.name, comment.comment_id)
        for fixture in gold_fixtures()
        for comment in fixture.comments
    }


def test_the_manifest_in_the_tree_parses_under_the_contract() -> None:
    """The manifest in the tree is a manifest the contract accepts.

    **Why this is a witness and not a read.** The contract lives in
    ``gold_manifest.py`` and the manifest in the tree is written by hand
    and by generator. A hand-written manifest that breaks one of the
    rules is a manifest the annotators cannot fill in, and the only
    symptom would be a refusal at the moment somebody tries.
    """
    assert MANIFEST.is_file(), (
        f"the manifest is not at {MANIFEST}. T02 ships it, and a gold set "
        "with no manifest is a corpus with nothing to annotate against."
    )
    parsed = validate_manifest(_document())
    assert parsed.items, "the manifest holds no item, so it describes nothing"
    assert parsed.partitions, "the manifest names no partition, so it cannot be split"


def test_every_item_names_a_comment_the_corpus_has() -> None:
    """The manifest and the corpus agree, item by item.

    **The drift this catches.** The corpus is generated and the manifest
    is written against it; regenerate the corpus with a different comment
    and the manifest still parses, still passes every rule, and still
    points at comments that are not there. The check is that every item
    names a comment the corpus has, and that its id is the one the id
    rules give it.
    """
    items = _document()["items"]
    assert items, "the manifest holds no item, so there is nothing to match"
    comments = _comments_in_the_corpus()

    for item in items:
        pair = (item["fixture"], item["comment_id"])
        assert pair in comments, (
            f"item {item['item_id']!r} names the comment {pair[1]!r} in "
            f"{pair[0]!r}, and the corpus has no such comment. The manifest and "
            "the corpus have drifted apart, and every rule in the manifest is "
            "still satisfied."
        )
        assert item["item_id"] == item_id(
            item["project_id"], item["version_id"], item["comment_id"]
        ), (
            f"item {item['item_id']!r} does not carry the id its own fields "
            "give it, so the manifest and the corpus are naming the same "
            "comment under two names."
        )


def test_the_corpus_section_records_the_bytes_that_are_written(tmp_path: Path) -> None:
    """The manifest's hashes are the hashes of the corpus that is written.

    **Why the binding matters.** The manifest binds itself to the corpus
    by ``sha256``, and that binding is worth nothing if the recorded
    digest is not the digest of the bytes a reviewer would regenerate.
    """
    document = _document()
    corpus = document["corpus"]
    assert corpus, "the manifest records no corpus, so it names no material"

    written = write_corpus(tmp_path / "written")
    for name, entry in corpus.items():
        path = written.get(name)
        assert path is not None, (
            f"the manifest records the manuscript {name!r} and the corpus does not write it."
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert entry["sha256"] == digest, (
            f"the manifest records {entry['sha256']!r} for {name!r} and the "
            f"bytes hash to {digest!r}. The record and the measurement "
            "disagree, and the measurement wins."
        )


def test_the_corpus_is_reproducible(tmp_path: Path) -> None:
    """The same manuscripts every time, so a reviewer can regenerate them.

    **Why the bytes matter.** A corpus that writes different bytes each
    run makes the manifest's hash a record of one accident, and the
    manifest cannot be checked against anything but itself.
    """
    first = write_corpus(tmp_path / "first")
    second = write_corpus(tmp_path / "second")
    assert first, "the corpus writes nothing, so there is nothing to reproduce"
    for name, path in first.items():
        assert path.read_bytes() == second[name].read_bytes(), (
            f"{name} was written twice and the two writes differ. A corpus "
            "whose bytes move makes the manifest's hash a record of one "
            "accident."
        )


def test_the_archive_entries_carry_no_clock(tmp_path: Path) -> None:
    """The archives carry no clock, which is what makes them reproducible.

    **Why this is a separate witness.** Two writes in the same second
    produce the same bytes even when the writer stamps the time, so
    comparing bytes alone cannot see a writer that has stopped pinning
    them — it only fails once the clock has moved on. **The clock is the
    mechanism**, and this checks it directly: every entry in every
    archive carries the same fixed moment, and that moment is the ZIP
    epoch rather than a time somebody could have written.
    """
    written = write_corpus(tmp_path / "written")
    assert written, "the corpus writes nothing, so there is nothing to read"
    for name, path in written.items():
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                assert info.date_time == _ZIP_EPOCH, (
                    f"the entry {info.filename!r} in {name} carries the time "
                    f"{info.date_time!r} rather than the ZIP epoch "
                    f"{list(_ZIP_EPOCH)!r}. A stamped time makes the bytes "
                    "depend on when they were written, and the manifest's "
                    "hashes bind to bytes."
                )


def test_the_feedback_ids_are_the_chains_own() -> None:
    """The manifest's feedback ids are the ids the chain computes.

    **Why this is not a formality.** The gold set is read against the
    chain's events, and the join is the feedback id. An id that was
    minted by the gold set's own rule would not join to anything, and
    the failure would be a silent empty result rather than an error.
    """
    from labcairn.papers.feedback import _feedback_id

    for item in _document()["items"]:
        assert item["feedback_id"] == _feedback_id(item["version_id"], item["comment_id"]), (
            f"item {item['item_id']!r} records the feedback id "
            f"{item['feedback_id']!r}, and the chain calls the same comment "
            f"{_feedback_id(item['version_id'], item['comment_id'])!r}. A row "
            "the manifest names is not the row the chain holds."
        )
        assert item["feedback_id"] == feedback_id(item["version_id"], item["comment_id"]), (
            f"item {item['item_id']!r} does not carry the feedback id the "
            "gold set's own rule derives for it."
        )


def test_the_annotations_are_all_or_nothing() -> None:
    """Every item carries the same state: no readings, or both and an arbiter.

    **The state in between is the one nobody can read.** A manifest with
    one reading on one item and two on the next is a manifest mid-flight,
    and it looks finished to anyone who counts the items rather than
    reading them. The gold set is either dispatched or it is not.
    """
    items = _document()["items"]
    readings = {len(item["annotations"]) for item in items}
    assert readings <= {0, 2}, (
        f"the manifest's items carry {sorted(readings)} annotations each. A "
        "gold set is dispatched with none, and finished with two on every "
        "item; anything else is a manifest half-read."
    )

    resolutions = {item.get("resolution") is not None for item in items}
    assert len(resolutions) == 1, (
        "some items have an arbiter's resolution and some do not, which is "
        "the same half-read state from the other side."
    )


def test_the_manifests_two_readings_are_by_two_different_readers() -> None:
    """The manifest in the tree has two readers on every item, and a third to arbitrate.

    **Why this is a witness and not a reading.** The manifest module
    refuses a manifest whose two readings share an annotator, and refuses
    one whose arbiter is one of its own annotators — **but those are
    refusals of a shape somebody typed**, and the file in the tree is a
    different thing: the gold set as it was actually written. **A rule
    that is not applied to the tree's own manifest is a rule that has
    never been applied to anything.**

    So this checks the tree's manifest directly, the way the rest of this
    file checks the tree's manifest directly: two readings, two different
    annotator ids, and an arbiter whose id is neither of theirs.

    **And it holds either way.** A manifest that has not been annotated
    carries no readings and no arbiter, and there is nothing here to say
    about it — so this says nothing about one, rather than insisting that
    it be empty.
    """
    items = _document()["items"]
    assert items, "the manifest holds no item, so there is nothing to read"

    for item in items:
        annotations = item["annotations"]
        if not annotations:
            continue

        readers = [annotation["annotator_id"] for annotation in annotations]
        assert len(set(readers)) == len(readers), (
            f"item {item['item_id']!r} carries two readings by {readers!r}. Two "
            "readings by one reader are one reading, and the agreement number "
            "over it is a statement about that reader's consistency."
        )
        assert len(readers) == 2, (
            f"item {item['item_id']!r} carries {len(readers)} reading(s). The "
            "gold set's shape is two readings and an arbiter's row."
        )

        resolution = item.get("resolution")
        assert resolution is not None, (
            f"item {item['item_id']!r} carries readings and no arbiter's row. A "
            "gold set is all or nothing: either nobody has read it or three "
            "people have."
        )
        arbiter = resolution["arbiter_id"]
        assert arbiter not in readers, (
            f"item {item['item_id']!r} names {arbiter!r} as its arbiter, and that "
            f"is one of its own readers ({readers!r}). An arbiter who is one of "
            "the two has read the item twice rather than arbitrated it."
        )


def test_the_completion_check_agrees_with_the_manifests_own_state() -> None:
    """The completion check passes a finished gold set and refuses an unfinished one.

    **Why this is written to hold either way.** The annotations were two
    people's work and an arbiter's, and nobody had done them when this file
    was written — so the manifest in the tree shipped empty, and the
    completion check refused it. **The witness does not insist on that
    emptiness**: it insists that the check reads whatever state the manifest
    is in correctly, so it will keep holding when the readings are written.
    **They have been written**, and the check passes.
    """
    manifest = load_manifest(MANIFEST)
    finished = all(
        len(item.annotations) == 2 and item.resolution is not None for item in manifest.items
    )

    if finished:
        require_annotated(manifest)
        return

    with pytest.raises(ValueError) as refusal:
        require_annotated(manifest)
    message = str(refusal.value)
    assert message.count("carries") == len(manifest.items), (
        f"the refusal has to name every item that is short, not the first one: {message!r}"
    )
