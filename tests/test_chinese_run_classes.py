r"""Every Chinese run in the tree is accounted for, in a class it is allowed to be in.

**The gap this closes.** Two measurements already exist and both measure *how
much* Chinese a file carries: the longest run (pinned in
``tests/test_no_reference_leakage.py``) and the whole load (pinned in
``tests/test_chinese_totals_pin.py``). Neither judges *what* a run is. A file
whose Chinese is the project's own ADRs reads the same as a file whose Chinese
is a sentence quoted from the manuscript, and -- the sharp case -- a run
replaced by a **different run of the same length** moves neither number, so
both pins stay green while the words change.

**The watch.** ``scripts/cjk_ceilings.py --classify`` records every Han run as
its ``(digest, length)`` in file order, and the registry
``tests/cjk_run_classes.json`` gives each run a class, with a one-line reason
per file. This file holds the registry against the tree: an added run, a
removed run, a reordered run or a changed run reddens, because the registry
records their digests rather than their text. A run's class must be one the
tree is allowed to carry -- and the allowed set is written here, not read from
the registry, so one file edited to relax the rule cannot hide itself.

**The classes.** ``project-voice`` (the project's own documents),
``design-quotation`` (the project's own execution design, quoted),
``product-vocabulary`` (Chinese the product or its tests must recognise),
``measurement`` (Han code points in the machinery that measures Chinese) and
``machine-output`` (a machine's string quoted as evidence) are allowed.
``corpus-quotation``, ``corpus-label`` and ``person-name`` are not: the tree's
promise is that nothing of the paper is in it, and a label carrying the
manuscript's title-of-record or a person's name is material too.

**How a run is classified, and how a new one gets a class.** The registry is
re-derived by ``python scripts/cjk_ceilings.py --classify --json``; a run whose
``(digest, length)`` is not in the registry is emitted as ``unclassified``,
which this file refuses. A person re-pins by recording the run's class in the
same commit -- an act visible in the diff, as a new long run is for the
ceiling. The Chinese itself is never written here: the digest identifies a
run, so a witness that watches the tree's Chinese does not add to it.

**What this file cannot see.** It cannot tell a quotation from the project's
own prose by the characters; it holds a judgment that a reader can re-derive
from the file and its reason. Two arms narrow the gap independently of the
registry: a run that is exactly a surname plus a title is refused whatever its
class, and the guard tests below prove that a short addition, and a same-length
replacement, are caught when both older pins stay put.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final, cast

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cjk_ceilings.py"
REGISTRY = Path(__file__).resolve().parent / "cjk_run_classes.json"

#: The classes a run may be in. Deliberately a second copy of the script's
#: ``ALLOWED_RUN_CLASSES`` and not an import: a mutation that relaxes one file
#: must leave the rule red in the other.
ALLOWED: Final[frozenset[str]] = frozenset(
    {
        "project-voice",
        "design-quotation",
        "product-vocabulary",
        "measurement",
        "machine-output",
    }
)

#: The classes a run must not be in. Named here so the guard test can prove
#: the allowedness arm refuses them, rather than only that the live tree
#: happens to carry none.
FORBIDDEN: Final[frozenset[str]] = frozenset({"corpus-quotation", "corpus-label", "person-name"})

_SYNTHETIC_BASE = 0x4E00


def _han(n: int, *, base: int = _SYNTHETIC_BASE) -> str:
    """n synthetic Han characters, constructed at runtime so this file spends none."""
    return "".join(chr(base + i) for i in range(n))


#: The same maximal-run shape the measurement uses, built from code points:
#: this file must not carry the Chinese it watches.
_HAN: Final[re.Pattern[str]] = re.compile(
    "["
    + chr(0x3400)
    + "-"
    + chr(0x4DBF)
    + chr(0x4E00)
    + "-"
    + chr(0x9FFF)
    + chr(0xF900)
    + "-"
    + chr(0xFAFF)
    + "]+"
)

#: Common Chinese surnames, by code point, and the titles a name label uses.
#: The shape this catches is narrow on purpose: a three-character run that is
#: exactly one surname followed by a two-character title. A name inside a
#: longer run is not caught by shape; the registry catches the run itself.
_SURNAMES: Final[str] = "".join(
    chr(cp)
    for cp in (
        0x674E,
        0x738B,
        0x5F20,
        0x5218,
        0x9648,
        0x6768,
        0x9EC4,
        0x8D75,
        0x5434,
        0x5468,
        0x5F90,
        0x5B59,
        0x9A6C,
        0x6731,
        0x80E1,
        0x90ED,
        0x4F55,
        0x9AD8,
        0x6797,
        0x7F57,
        0x90D1,
        0x6881,
        0x8C22,
        0x5B8B,
        0x5510,
        0x8BB8,
        0x97E9,
        0x51AF,
        0x9093,
        0x66F9,
        0x5F6D,
        0x66FE,
        0x8096,
        0x7530,
        0x8463,
        0x8881,
        0x6F58,
        0x848B,
        0x8521,
        0x4F59,
        0x675C,
        0x53F6,
        0x7A0B,
        0x82CF,
        0x9B4F,
        0x5415,
        0x4E01,
        0x4EFB,
        0x6C88,
        0x59DA,
        0x5362,
        0x59DC,
        0x5D14,
        0x949F,
        0x8C2D,
        0x9646,
        0x6C6A,
        0x8303,
        0x91D1,
        0x77F3,
        0x5ED6,
        0x8D3E,
        0x590F,
        0x97E6,
        0x65B9,
        0x767D,
        0x90B9,
        0x5B5F,
        0x718A,
        0x79E6,
        0x90B1,
        0x6C5F,
        0x5C39,
        0x859B,
        0x6BB5,
        0x96F7,
        0x4FAF,
        0x9F99,
        0x53F2,
        0x9676,
        0x9ECE,
        0x8D3A,
        0x987E,
        0x6BDB,
        0x90DD,
        0x9F9A,
        0x90B5,
        0x4E07,
        0x94B1,
        0x4E25,
        0x8983,
        0x6B66,
        0x6234,
        0x83AB,
        0x5B54,
        0x5411,
        0x6C64,
    )
)

_TITLES: Final[tuple[str, ...]] = tuple(
    "".join(chr(cp) for cp in pair)
    for pair in (
        (0x8001, 0x5E08),
        (0x6559, 0x6388),
        (0x5BFC, 0x5E08),
        (0x533B, 0x751F),
        (0x4E3B, 0x4EFB),
        (0x535A, 0x58EB),
        (0x5148, 0x751F),
        (0x5973, 0x58EB),
        (0x7ECF, 0x7406),
        (0x9662, 0x58EB),
        (0x6821, 0x957F),
        (0x9662, 0x957F),
    )
)


def _name_shaped_runs(text: str) -> list[str]:
    """Runs that are exactly one surname and one title: a label carrying a name."""
    out: list[str] = []
    for match in _HAN.finditer(text):
        run = match.group(0)
        if len(run) == 3 and run[0] in _SURNAMES and run[1:] in _TITLES:
            out.append(run)
    return out


def _str(value: object) -> str:
    assert isinstance(value, str)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _load(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"not a JSON object: {path}"
    return cast(dict[str, object], data)


def _files(registry: dict[str, object]) -> dict[str, object]:
    files = registry.get("files")
    assert isinstance(files, dict), "registry has no 'files' object"
    return cast(dict[str, object], files)


def _runs(entry: object) -> list[list[object]]:
    assert isinstance(entry, dict), "a registry entry is not an object"
    runs = entry.get("runs")
    assert isinstance(runs, list), "a registry entry has no 'runs' list"
    return cast(list[list[object]], runs)


def _canonical(registry: dict[str, object]) -> dict[str, list[tuple[str, int, str]]]:
    """path -> ordered (digest, length, class), the form both sides are compared in."""
    out: dict[str, list[tuple[str, int, str]]] = {}
    for rel, entry in _files(registry).items():
        out[rel] = [(_str(row[0]), _int(row[1]), _str(row[2])) for row in _runs(entry)]
    return out


def _run_tool(root: Path, *args: str) -> str:
    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            str(SCRIPT),
            *args,
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout


def _classification(root: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(_run_tool(root, "--classify", "--json")))


def _measure(root: Path, flag: str) -> dict[str, int]:
    return cast(dict[str, int], json.loads(_run_tool(root, flag)))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _scratch_repo(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "scratch"
    (repo / "docs").mkdir(parents=True)
    _git(repo, "init")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "scratch"\nversion = "0"\n', encoding="utf-8"
    )
    (repo / "docs" / "notes.md").write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed")
    return repo


def _pin(repo: Path, classification: dict[str, object], cls: str) -> Path:
    """Write the classification back as the registry, every run in one class."""
    for entry in _files(classification).values():
        for row in _runs(entry):
            row[2] = cls
    path = repo / "tests" / "cjk_run_classes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(classification, ensure_ascii=False), encoding="utf-8")
    return path


def test_every_chinese_run_in_the_tree_is_classified(repo_root: Path) -> None:
    """The registry and the tree agree about every run: digest, length and class.

    A difference in either direction reddens: an added run is a run nobody
    classified, a removed run is a value that was carried forward instead of
    re-measured, and a changed digest is a run whose text moved while its
    length -- and the file's totals -- did not.
    """
    measured = _canonical(_classification(repo_root))
    pinned = _canonical(_load(REGISTRY))

    assert set(measured) == set(pinned), (
        "the files carrying Chinese have changed since the classification was "
        f"pinned: added={sorted(set(measured) - set(pinned))} "
        f"removed={sorted(set(pinned) - set(measured))}"
    )
    for rel in sorted(measured):
        assert measured[rel] == pinned[rel], (
            f"the Chinese runs of {rel} have changed since they were classified. "
            f"measured={measured[rel]!r} pinned={pinned[rel]!r}. A new run is "
            "classified by recording it in tests/cjk_run_classes.json in the "
            "commit that adds it, or it is removed; a run whose text changed is "
            "not a run any class was written for"
        )


def test_every_run_carries_an_allowed_class() -> None:
    """No run is in a class the tree is not allowed to carry, and every class is known."""
    pinned = _canonical(_load(REGISTRY))
    classes = {cls for runs in pinned.values() for _, _, cls in runs}
    assert classes <= ALLOWED, (
        f"the tree carries runs in classes it is not allowed to carry: "
        f"{sorted(classes - ALLOWED)}; the forbidden classes are {sorted(FORBIDDEN)}"
    )


def test_the_allowedness_arm_refuses_a_forbidden_class() -> None:
    """The arm is live: a registry with a corpus quotation in it is refused.

    Without this, the allowedness test could pass because every class the
    registry happens to hold is allowed -- which is not the same property.
    """
    registry = _load(REGISTRY)
    entry = next(iter(_files(registry).values()))
    _runs(entry)[0][2] = "corpus-quotation"
    classes = {cls for runs in _canonical(registry).values() for _, _, cls in runs}
    assert classes - ALLOWED == {"corpus-quotation"}


def test_no_run_is_a_label_carrying_a_name() -> None:
    """No run in the tree is exactly a surname plus a title.

    This is the shape the earlier records carried and this batch removed. It
    is checked independently of the registry, so a registry re-pin that
    mislabels such a run as allowed does not make it invisible.
    """
    registry = _load(REGISTRY)
    offenders: list[tuple[str, str]] = []
    for rel in sorted(_files(registry)):
        text = (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")
        offenders.extend((rel, run) for run in _name_shaped_runs(text))
    assert offenders == [], (
        "a run in the tree is a label of the shape surname + title, which is a "
        f"name label: {offenders!r}. It is redacted in place, the way the batch "
        "that found the first one did, and the record says why"
    )


def test_the_name_shape_arm_catches_a_label() -> None:
    """The arm is live: a synthetic surname plus title is caught."""
    label = _han(1, base=0x674E) + _TITLES[0]
    assert _name_shaped_runs(f"text {label} text") == [label]


def test_a_short_run_is_caught_even_though_the_longest_run_does_not_move(
    tmp_path: Path,
) -> None:
    """The case both older pins are blind to, watched from the new direction.

    A four-character run appended to a file whose longest run is seven leaves
    the longest-run measurement at seven; the totals pin would see it only as
    a number. The classification records the new run itself, as
    ``unclassified``, so the person who added it must say what it is.
    """
    long_run = _han(7)
    repo = _scratch_repo(tmp_path, f"seed\n{long_run}\n")
    baseline = _classification(repo)
    _pin(repo, baseline, "project-voice")

    (repo / "docs" / "notes.md").write_text(f"seed\n{long_run}\n{_han(4)}\n", encoding="utf-8")
    _git(repo, "add", "docs/notes.md")
    _git(repo, "commit", "-m", "append a short run")

    longest = _measure(repo, "--json")
    totals = _measure(repo, "--totals")
    assert longest["docs/notes.md"] == 7, (
        "the longest run must stay put when a shorter run is appended; this is "
        "the measurement's blind direction, not this witness's"
    )
    assert totals["docs/notes.md"] == 11, "the short run did move the totals"

    after = _canonical(_classification(repo))
    assert len(after["docs/notes.md"]) == 2, (
        "the classification must record both runs, not only the longest one"
    )
    assert after["docs/notes.md"][1][2] == "unclassified", (
        "a run added since the pin is unclassified until a person says what it is"
    )


def test_a_same_length_replacement_is_caught(tmp_path: Path) -> None:
    """Neither older pin can see this: a run replaced by a different run of equal length.

    The longest run is the same number and the total is the same number, so
    both pins stay green; the run's digest is different, so the classification
    reddens.
    """
    first = _han(7)
    second = _han(7, base=0x5B00)
    assert first != second and len(first) == len(second)
    repo = _scratch_repo(tmp_path, f"seed\n{first}\n")
    baseline = _classification(repo)
    _pin(repo, baseline, "project-voice")

    (repo / "docs" / "notes.md").write_text(f"seed\n{second}\n", encoding="utf-8")
    _git(repo, "add", "docs/notes.md")
    _git(repo, "commit", "-m", "replace the run at equal length")

    assert _measure(repo, "--json")["docs/notes.md"] == 7
    assert _measure(repo, "--totals")["docs/notes.md"] == 7
    after = _canonical(_classification(repo))
    pinned = _canonical(_load(repo / "tests" / "cjk_run_classes.json"))
    assert after["docs/notes.md"][0][0] != pinned["docs/notes.md"][0][0], (
        "the digest must move when the run's text moves, even at equal length"
    )
    assert after["docs/notes.md"][0][2] == "unclassified", (
        "a replaced run is a run nobody classified; it does not inherit the old run's class"
    )


def test_the_registry_is_derivable_and_round_trips(repo_root: Path) -> None:
    """``--classify --json`` against the pinned registry reproduces it exactly.

    A reader re-derives the classification by running the tool. If the tool's
    output drifted from the registry without a run changing, the two differ
    here -- which is what makes the registry a measurement rather than an
    assertion.
    """
    assert _classification(repo_root) == _load(REGISTRY)


@pytest.mark.parametrize(
    "rel",
    ["tests/cjk_run_classes.json", "tests/test_chinese_run_classes.py"],
)
def test_the_registry_carries_no_chinese(repo_root: Path, rel: str) -> None:
    """The registry, and this witness's own bytes, spend none of the budget they hold."""
    text = (repo_root / rel).read_text(encoding="utf-8")
    assert _HAN.findall(text) == [], (
        f"{rel} carries Han characters; the classification identifies runs by "
        "digest so that watching the tree's Chinese does not add to it"
    )
