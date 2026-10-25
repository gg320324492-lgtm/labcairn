"""The protocol, read out of ``docs/EVALUATION.md``.

**Why this module exists.** The protocol is a document, and a document is
not a program. The harness has to know the protocol's gate classes, its
metrics and its blockers — but a harness that *carries a copy* of that list
is a harness that goes stale the moment the protocol changes, and it goes
stale **silently**: the copy keeps answering, and the answer is about a
protocol that is no longer the one in force.

So the list is **parsed out of the protocol file at run time**. The
consequences are the point:

* The report's class names, class definitions, metric texts and blocker
  texts are the protocol's own words, not this repository's paraphrase of
  them. A reader can check the report against the protocol by reading the
  protocol.
* Editing ``docs/EVALUATION.md`` changes what the harness reports, because
  the harness reads it. The protocol is the ruler, and a ruler that is
  re-measured is still a ruler.
* A protocol item with no witness in this repository is **visible** as such,
  because the parser found it and the manifest did not.

**What this module deliberately does not do.** It does not *interpret* the
protocol, and it does not soften it. The protocol says that a result is a
benchmark only when it is measured on immutable fixture and version labels,
and that superiority may not be claimed without like-for-like matched-task
baselines, verified capabilities, and documented confidence intervals or
limitations. Those two sentences are extracted and carried into the report
verbatim, and the comparison section enforces the second of them.

**The parsing is a mechanism, and it is watched.** A parser that silently
returns nothing would make the harness report an empty, green run — the
worst possible failure for a tool whose whole job is to report honestly. So
:func:`parse_protocol` raises when the protocol file does not contain the
sections it expects, and ``tests/test_evaluation_harness.py`` watches that
the parse yields the five gate classes, the metrics and the blockers rather
than an empty tuple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The protocol, relative to the repository root.
PROTOCOL_RELATIVE_PATH: Final[Path] = Path("docs") / "EVALUATION.md"

#: The headings the parser looks for. Each is a section of the protocol, and
#: the parser refuses to answer if one is missing — a missing section is a
#: protocol that changed shape, and the harness must say so rather than
#: report on a protocol that is not there.
GATE_CLASSES_HEADING: Final = "## Mandatory automated gates"
METRICS_HEADING: Final = "## Metrics to report with denominators and failure cases"
BLOCKERS_HEADING: Final = "## Phase 1 blockers"

#: A numbered item under the gate-classes heading: ``1. Unit: ...``.
_NUMBERED_ITEM: Final = re.compile(r"^\s*\d+\.\s+(?P<label>[^:]+):\s*(?P<body>.+?)\s*$")

#: A bulleted item under a heading.
_BULLET_ITEM: Final = re.compile(r"^\s*[-*]\s+(?P<body>\S.*?)\s*$")

#: The sentence that forbids an invented superiority, and the one that says
#: when a result is a benchmark. Both are carried into the report verbatim.
_SUPERIORITY_MARKER: Final = "Do not claim superiority"
_BENCHMARK_MARKER: Final = "Results are benchmarks only when"


@dataclass(frozen=True, slots=True)
class GateClass:
    """One of the protocol's mandatory automated gate classes."""

    #: The machine key: the label, lowercased, with spaces and hyphens folded
    #: to underscores. ``Real-model smoke`` becomes ``real_model_smoke``.
    key: str
    #: The protocol's own name for the class.
    label: str
    #: The protocol's own definition, from the text after the colon.
    definition: str
    #: Whether the harness can run this class without a credential.
    runnable_offline: bool
    #: Why the class is not runnable offline, when it is not.
    offline_reason: str


@dataclass(frozen=True, slots=True)
class Metric:
    """One of the protocol's metrics to report with denominators."""

    #: The short key the manifest's witnesses are filed under.
    key: str
    #: The protocol's own wording.
    text: str


@dataclass(frozen=True, slots=True)
class Blocker:
    """One of the protocol's Phase 1 blockers."""

    #: The short key the manifest's witnesses are filed under.
    key: str
    #: The protocol's own wording.
    text: str


@dataclass(frozen=True, slots=True)
class Protocol:
    """Everything the harness takes from ``docs/EVALUATION.md``."""

    #: Where the protocol was read from.
    path: Path
    #: The mandatory automated gate classes, in the protocol's order.
    gate_classes: tuple[GateClass, ...]
    #: The metrics to report, in the protocol's order.
    metrics: tuple[Metric, ...]
    #: The Phase 1 blockers, in the protocol's order.
    blockers: tuple[Blocker, ...]
    #: The protocol's sentence on when a result is a benchmark.
    benchmark_clause: str
    #: The protocol's sentence forbidding an invented superiority.
    superiority_clause: str

    def gate_class(self, key: str) -> GateClass:
        """The class with this key.

        Raises rather than returning a default: a caller that asks for a
        class the protocol does not define has a bug, and a default value
        would hide it behind a plausible-looking row.
        """
        for candidate in self.gate_classes:
            if candidate.key == key:
                return candidate
        msg = f"the protocol defines no gate class named {key!r}"
        raise KeyError(msg)

    def metric(self, key: str) -> Metric:
        """The metric with this key."""
        for candidate in self.metrics:
            if candidate.key == key:
                return candidate
        msg = f"the protocol defines no metric named {key!r}"
        raise KeyError(msg)

    def blocker(self, key: str) -> Blocker:
        """The blocker with this key."""
        for candidate in self.blockers:
            if candidate.key == key:
                return candidate
        msg = f"the protocol defines no blocker named {key!r}"
        raise KeyError(msg)


def _section(text: str, heading: str) -> list[str]:
    """The lines of one ``##`` section, without the heading.

    A heading that is not there is an error, not an empty section: the
    harness's job is to report on *this* protocol, and a missing section
    means it is reading something else.
    """
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        msg = f"{heading!r} is not a section of the protocol"
        raise ValueError(msg) from None
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def _bullets(lines: list[str]) -> list[str]:
    """The bulleted items of a section."""
    items = []
    for line in lines:
        match = _BULLET_ITEM.match(line)
        if match is not None:
            items.append(match.group("body"))
    return items


def _sentence_containing(text: str, marker: str) -> str:
    """The sentence of ``text`` that contains ``marker``.

    The protocol writes both clauses as one line, so the line is split on
    sentence boundaries and the piece carrying the marker is taken. A
    marker that is not there is an error: the clause is one the report
    quotes, and a report that quotes an empty string has stopped quoting.
    """
    for line in text.splitlines():
        if marker not in line:
            continue
        for sentence in re.split(r"(?<=\.)\s+", line.strip()):
            if marker in sentence:
                return sentence
    msg = f"the protocol carries no sentence containing {marker!r}"
    raise ValueError(msg)


def _slug(label: str) -> str:
    """A machine key for a gate-class label."""
    return label.strip().lower().replace(" ", "_").replace("-", "_")


def parse_protocol(
    path: Path,
    metric_prefixes: dict[str, str],
    blocker_prefixes: dict[str, str],
    offline_classes: dict[str, tuple[bool, str]],
) -> Protocol:
    """Read the protocol out of ``path``.

    ``metric_prefixes`` and ``blocker_prefixes`` map a lowercased prefix of
    the protocol's wording onto the short key the rest of the harness files
    it under. A protocol item that matches no prefix is an error rather
    than a silently unwitnessed row: the harness is telling the caller that
    the protocol has grown an item this repository has no witnesses for,
    and the caller's witness table is what has to answer it.
    """
    text = path.read_text(encoding="utf-8")

    classes: list[GateClass] = []
    for line in _section(text, GATE_CLASSES_HEADING):
        match = _NUMBERED_ITEM.match(line)
        if match is None:
            continue
        label = match.group("label").strip()
        key = _slug(label)
        runnable, reason = offline_classes.get(key, (True, ""))
        classes.append(
            GateClass(
                key=key,
                label=label,
                definition=match.group("body").strip(),
                runnable_offline=runnable,
                offline_reason=reason,
            )
        )

    metrics: list[Metric] = []
    for body in _bullets(_section(text, METRICS_HEADING)):
        key = _match_prefix(body, metric_prefixes)
        metrics.append(Metric(key=key, text=body))

    blockers: list[Blocker] = []
    for body in _bullets(_section(text, BLOCKERS_HEADING)):
        key = _match_prefix(body, blocker_prefixes)
        blockers.append(Blocker(key=key, text=body))

    if not classes:
        msg = f"the protocol at {path} names no gate class"
        raise ValueError(msg)
    if not metrics:
        msg = f"the protocol at {path} names no metric"
        raise ValueError(msg)
    if not blockers:
        msg = f"the protocol at {path} names no blocker"
        raise ValueError(msg)

    return Protocol(
        path=path,
        gate_classes=tuple(classes),
        metrics=tuple(metrics),
        blockers=tuple(blockers),
        benchmark_clause=_sentence_containing(text, _BENCHMARK_MARKER),
        superiority_clause=_sentence_containing(text, _SUPERIORITY_MARKER),
    )


def _match_prefix(text: str, prefixes: dict[str, str]) -> str:
    """The key whose prefix this text starts with.

    The longest matching prefix wins, so that a short prefix cannot shadow
    a longer one that starts the same way.
    """
    lowered = text.lower()
    best: str | None = None
    best_length = -1
    for prefix, key in prefixes.items():
        if lowered.startswith(prefix) and len(prefix) > best_length:
            best = key
            best_length = len(prefix)
    if best is None:
        msg = (
            f"no witness key matches {text!r}; the protocol has grown an item "
            "this harness has no witnesses for, and the witness table has to "
            "answer it"
        )
        raise ValueError(msg)
    return best


def protocol_path(repo_root: Path) -> Path:
    """Where the protocol lives, given the repository root."""
    return repo_root / PROTOCOL_RELATIVE_PATH
