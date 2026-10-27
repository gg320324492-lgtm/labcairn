"""The evaluation harness — one command that runs the protocol and reports it.

**What this is.** ``docs/EVALUATION.md`` is the protocol this gate measures
against, and it is a document, not a program: it names five mandatory
automated gate classes, seven metrics to report with denominators and
failure cases, and the Phase 1 blockers. Nothing in the repository ran it.

This package runs it. ``python -m tests.evaluation`` runs the protocol's gate
classes, parses the outcomes, and writes a report in which **every number
carries its denominator**, the **failure cases are listed rather than
averaged away**, a **skipped blocking test counts as a failure**, and the
classes that were **not run are named with the reason**.

**Why it reads the protocol rather than restating it.** A harness that
carries its own copy of the protocol's list is a harness that goes stale the
moment the protocol changes, and it goes stale *silently*: the copy keeps
answering, and the answer is about a protocol that no longer exists. So the
vocabulary — the gate classes, the metrics, the blockers, and the sentence
that forbids an invented superiority — is **parsed out of
``docs/EVALUATION.md``** at run time, and the file this package ships is
never edited to match it.

**What it does not do.** It does not measure the product's task-level
metrics, because a number that is not a measurement of the product is a
number with a denominator and no numerator. Where the protocol asks for
something this run cannot produce — a human-checked sample, a real
provider, a task-level corpus — the report says **NOT MEASURED** and says
why, and that statement is part of the report rather than an omission from
it. The protocol's own rule is quoted in the report and enforced by the
comparison section: no ranking is printed unless the comparison is
like-for-like.

**The pieces.**

* :mod:`evaluation.protocol` — parses ``docs/EVALUATION.md``.
* :mod:`evaluation.manifest` — the partition of the repository's test
  files over the protocol's gate classes, and the witnesses for each metric
  and each blocker.
* :mod:`evaluation.runner` — runs a class's files as a pytest
  subprocess.
* :mod:`evaluation.junit` — reads pytest's JUnit XML.
* :mod:`evaluation.corpus` — measures the corpus against the committed
  answer key.
* :mod:`evaluation.public_corpus` — measures the **public fixture corpus**
  against its own answer key, and it is what makes the protocol's
  abstention metric measurable at all.
* :mod:`evaluation.faults` — reads the crash matrix's fault-injection
  coverage out of the matrix.
* :mod:`evaluation.shards` — reads the required CI tests out of the CI's
  own shard file.
* :mod:`evaluation.aggregate` — turns outcomes into class, blocker and
  metric results.
* :mod:`evaluation.comparison` — decides whether a baseline may be
  compared at all.
* :mod:`evaluation.report` — renders the report, as Markdown and JSON.
* :mod:`evaluation.cli` — the one command.

**Why this package puts ``tests/`` on the path.** The harness reuses the
repository's own corpus helper, ``tests/analysis_fixtures.py``, and the
repository's test suite imports that helper by its **bare** name — ``from
analysis_fixtures import ...`` — because ``tests/`` is what pytest puts on
the path for a test module. So the harness does the same thing here, in the
one place where it can: its own package initialiser. Without this,
``python -m tests.evaluation`` would find the helper under a different name
than the test suite does, and the corpus's addressing rules would be read
twice, under two names.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: The directory the repository's test support modules live in.
_TESTS_DIR: Path = Path(__file__).resolve().parent.parent

if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

__all__: list[str] = []
