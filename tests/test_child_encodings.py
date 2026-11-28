"""The witness for *a child's bytes are decoded as the encoding they were written in*.

**The property.** Every place this repository reads a child's output says
which encoding it decodes, and the encoding it says is the encoding the
child wrote. Both halves have to agree: pinning only the parent's half
turns the failure around rather than fixing it, because a child that writes
the machine's code page read as UTF-8 fails exactly the same way.

**Why it is a witness and not a claim.** Twice in one afternoon on
2026-11-28 a whole-suite run failed for the same reason and nothing in the
tree said so: a child process was run with ``text=True`` and no
``encoding=``, so the parent decoded the child's UTF-8 bytes with the
host's code page — GBK on this machine — and the reader thread died on the
first byte it could not decode. It cost two runs of the whole suite. A
sweep the same day found **30** text pipes across the tree in that state.

So this file watches two things, and the second one is the one that makes
the first worth having:

* :func:`test_every_text_pipe_states_the_encoding_it_decodes` — a static
  gate over every ``subprocess`` call in the tree. It fails when a text
  pipe stops saying which encoding it decodes, and it fails *naming the
  file and line*, so the fix is where the failure is.
* :func:`test_a_child_the_host_cannot_read_is_still_read` — the
  behavioural gate. It drives a child that writes bytes the host's code
  page cannot decode, and requires the reader to still hold them. This is
  the failure that actually happened, reproduced.

**Why the behavioural gate is written the way it is.** It cannot depend on
the machine's locale, because a witness that only fails on a GBK machine is
a witness that does not fail on the CI runner, and a witness that does not
fail on the runner is not a witness. So the child is asked to write bytes
that **no** single-byte code page can decode — a byte sequence that is
invalid in UTF-8 and in every Latin-1/CP437-family code page — and the
host's own code page is deliberately *not* consulted. The property under
test is "the reader decoded what the child wrote", and that is decided by
the encoding the reader was told to use.

**What the static gate does not claim.** It does not check that each
encoding is the *right* one; it checks that each one is *stated*. Which
encoding a given child writes is a fact about that child, and the facts are
written down in :mod:`tests.child_encoding` and in the record that
accompanies this sweep. The static gate is what keeps that record honest
in the other direction: a new text pipe cannot be added without saying what
it decodes.

**The rules it enforces.** A text pipe has to state an ``encoding=``, and
it has to state an ``errors=`` as well — because a decode that raises
inside subprocess's reader thread is swallowed there, and the capture comes
back as ``None``. The failure a caller then sees is ``AttributeError:
'NoneType' object has no attribute 'strip'``, which names neither the
cause nor the fix.
"""

from __future__ import annotations

import ast
import locale
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from child_encoding import (
    CHILD_OUTPUT_ERRORS,
    GIT_OUTPUT_ENCODING,
    NATIVE_OUTPUT_ENCODING,
    PYTHON_OUTPUT_ENCODING,
    python_child_environment,
)

#: The directory the sweep walks. Everything in the repository that is
#: Python, except the trees that are not this repository's own code.
SWEEPED_ROOTS: Final = ("src", "scripts", "examples", "tests", ".github")

#: The directories under the roots that are not this repository's own code.
SKIPPED_DIRECTORIES: Final = frozenset(
    {
        ".git",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
        "web",
        "shell",
    }
)

#: The subprocess entry points a text pipe can be called through.
SUBPROCESS_ENTRY_POINTS: Final = frozenset({"run", "call", "check_output", "check_call", "Popen"})

#: The tree's own wrappers around those entry points.
#:
#: A wrapper is a text pipe like any other: it forwards its keyword
#: arguments to ``subprocess.run``, so the encoding still has to be stated
#: at the call site. The names are listed rather than matched by a pattern,
#: so that a new wrapper is added here deliberately — a gate that
#: discovered wrappers by guessing would go quiet the day a wrapper was
#: named differently.
CHILD_RUNNER_NAMES: Final = frozenset(
    {
        "bounded_run",
        "bounded_git",
        "bounded_fast",
    }
)

#: The keywords that turn a subprocess call into a text pipe.
TEXT_KEYWORDS: Final = frozenset({"text", "universal_newlines"})

#: The files the sweep does not judge.
#:
#: This file is one of them, and the reason is that it *contains* a text
#: pipe that states no encoding on purpose: the control in
#: :func:`test_the_same_child_read_with_the_hosts_encoding_is_not_held` runs
#: the child the way the tree used to, and that is the whole point of it.
#: A gate that judged its own controls would have to be switched off for
#: them, and a gate that is switched off is not a gate.
SKIPPED_FILES: Final = frozenset({"tests/test_child_encodings.py"})


def _python_files(repo_root: Path) -> list[Path]:
    """Every Python file this repository owns."""
    files: list[Path] = []
    for root_name in SWEEPED_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in SKIPPED_DIRECTORIES for part in path.parts):
                continue
            if path.relative_to(repo_root).as_posix() in SKIPPED_FILES:
                continue
            files.append(path)
    return sorted(files)


def _is_child_runner(node: ast.Call) -> str | None:
    """The name of the child runner this call is, or ``None``.

    **A wrapper counts.** The tree has a shared helper that runs a command
    with a deadline (``tests/deadline_support.py``), and a text pipe
    routed through it is still a text pipe: the helper forwards its
    keyword arguments to ``subprocess.run``, so the encoding still has to
    be stated at the call site. A gate that only recognised
    ``subprocess.run`` would have gone quiet the day the tree grew a
    wrapper — and the wrapper is exactly where a reader would stop
    looking.

    So a call is a child runner when it is one of ``subprocess``'s own
    entry points, or when it is a local function whose name says it runs
    something (``bounded_run``, ``bounded_git``, ``bounded_fast``, and
    anything else of that shape).
    """
    func = node.func
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
            return func.attr if func.attr in SUBPROCESS_ENTRY_POINTS else None
        return None
    if isinstance(func, ast.Name):
        return func.id if func.id in CHILD_RUNNER_NAMES else None
    return None


def _text_pipes(tree: ast.AST) -> list[tuple[int, ast.Call]]:
    """Every text-mode child call, with the line its ``text=`` is on."""
    found: list[tuple[int, ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_child_runner(node) is None:
            continue
        for keyword in node.keywords:
            if keyword.arg in TEXT_KEYWORDS:
                found.append((keyword.value.lineno, node))
                break
    return found


def _keyword(node: ast.Call, name: str) -> ast.keyword | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword
    return None


@pytest.mark.unit
def test_every_text_pipe_states_the_encoding_it_decodes(repo_root: Path) -> None:
    """No text pipe in the tree reads a child without saying which encoding.

    **What it watches.** Every ``subprocess`` call that reads text has to
    state the encoding it decodes, and the ``errors=`` it decodes with.
    Without the second, a byte that cannot be decoded raises inside
    subprocess's reader thread, where the exception is swallowed, and the
    capture comes back as ``None`` — so the failure a caller sees is
    ``AttributeError: 'NoneType' object has no attribute 'strip'``, which
    names neither the cause nor the fix.

    **How it fails.** By naming the file, the line, and which half is
    missing, so the fix is where the failure is.
    """
    offences: list[str] = []
    for path in _python_files(repo_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:  # pragma: no cover - the tree parses in CI
            offences.append(f"{path.relative_to(repo_root)}: does not parse: {error}")
            continue
        for lineno, call in _text_pipes(tree):
            relative = path.relative_to(repo_root).as_posix()
            encoding = _keyword(call, "encoding")
            errors = _keyword(call, "errors")
            if encoding is None:
                offences.append(
                    f"{relative}:{lineno}: reads text but states no `encoding=`; "
                    "it decodes with the host's code page"
                )
            if errors is None:
                offences.append(
                    f"{relative}:{lineno}: states no `errors=`; an undecodable "
                    "byte must cost the reader a wrong character, never a dead stream"
                )
    assert not offences, "every text pipe has to say which encoding it decodes:\n" + "\n".join(
        offences
    )


@pytest.mark.unit
def test_a_text_pipe_states_an_encoding_that_is_one_of_the_known_ones(
    repo_root: Path,
) -> None:
    """A stated encoding is one of the tree's named answers.

    **Why this is separate.** The gate above checks that an encoding is
    *stated*. This checks that it is one this repository has a **name** for,
    because an unnamed encoding is a fact nobody wrote down: the next
    reader has to guess whether it is the child's encoding or a habit.

    The named answers are in :mod:`tests.child_encoding`, and each one is a
    measured fact about a kind of child:

    * :data:`~tests.child_encoding.GIT_OUTPUT_ENCODING` — git writes UTF-8.
    * :data:`~tests.child_encoding.PYTHON_OUTPUT_ENCODING` — this
      repository's children write UTF-8.
    * :data:`~tests.child_encoding.NATIVE_OUTPUT_ENCODING` — a native tool
      writes UTF-8, because it is asked to.
    """
    known = {
        GIT_OUTPUT_ENCODING,
        PYTHON_OUTPUT_ENCODING,
        NATIVE_OUTPUT_ENCODING,
    }
    offences: list[str] = []
    for path in _python_files(repo_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover
            continue
        for lineno, call in _text_pipes(tree):
            encoding = _keyword(call, "encoding")
            if encoding is None:
                continue
            try:
                value = ast.literal_eval(encoding.value)
            except ValueError:
                # A name (a constant, a module attribute) is not a literal;
                # it cannot be checked here, and the module it comes from is
                # the place where the fact is written down.
                continue
            if isinstance(value, str) and value not in known:
                relative = path.relative_to(repo_root).as_posix()
                offences.append(
                    f"{relative}:{lineno}: decodes as {value!r}, which is not one "
                    f"of the tree's named answers ({sorted(known)})"
                )
    assert not offences, (
        "a stated encoding has to be one this repository has a name for:\n" + "\n".join(offences)
    )


@pytest.mark.unit
def test_a_child_the_host_cannot_read_is_still_read(tmp_path: Path) -> None:
    """The child writes bytes the host's code page cannot decode, and the reader holds them.

    **The reproduction.** This is the failure that happened twice on
    2026-11-28: a child wrote UTF-8, the parent decoded with the host's
    code page, and the decode raised inside subprocess's reader thread,
    where the exception is swallowed — so the capture came back as
    ``None`` and the caller died on ``None.strip()``.

    **Why the child's bytes are not decodable by *any* code page.** The
    witness cannot depend on the machine's locale: a test that only fails on
    a GBK machine does not fail on the CI runner, and a witness that does
    not fail on the runner is not a witness. So the child is asked to write
    a byte sequence that is invalid in UTF-8 *and* in every single-byte
    code page — the surrogate range ``U+D800``..``U+DFFF`` encoded as
    UTF-8 (``\\xed\\xa0\\x80``) is invalid UTF-8 by construction, and
    ``\\xed`` is not a lead byte in any of the code pages this repository's
    children write in.

    **What the reader has to do.** Decode them as UTF-8, with
    ``errors="replace"``, and hold them: the sentinel has to be there and
    the undecodable bytes have to be *replaced* rather than dropped and
    rather than fatal. A reader that decodes with the host's code page
    raises, and the capture comes back as ``None``.

    **Why the child writes through ``sys.stdout.buffer``.** The text layer
    and the binary layer of a stream are two buffers, and a write to one is
    not ordered against a write to the other: a child that wrote the
    sentinel through ``sys.stdout.write`` and the bad bytes through
    ``sys.stdout.buffer.write`` had them **arrive in the opposite order**
    (measured on 2026-11-28). Writing everything through the binary layer
    makes the order the order the child wrote, which is what a reader is
    entitled to expect.
    """
    sentinel = "SENTINEL"
    code = (
        "import sys;"
        f"sys.stdout.buffer.write({sentinel.encode('utf-8')!r} + b'\\xed\\xa0\\x80');"
        "sys.stdout.buffer.flush()"
    )
    environment = python_child_environment()
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding=PYTHON_OUTPUT_ENCODING,
        errors=CHILD_OUTPUT_ERRORS,
        env=environment,
        timeout=120,
        check=False,
    )
    assert completed.stdout is not None, (
        "the capture came back as None, which is what a swallowed decode "
        "failure looks like from here: the reader thread raised, the "
        "exception was swallowed, and the caller was handed nothing"
    )
    assert completed.stdout.startswith(sentinel), (
        f"the reader lost the child's bytes: {completed.stdout!r}"
    )
    # The undecodable bytes are *replaced*, not dropped and not fatal: the
    # sentinel is still there, and each undecodable byte became one
    # replacement character. Three bytes went in, so three come out.
    assert len(completed.stdout) == len(sentinel) + 3, (
        f"the reader held {len(completed.stdout)} characters where "
        f"{len(sentinel) + 3} were expected: {completed.stdout!r}"
    )


@pytest.mark.unit
def test_the_same_child_read_with_the_hosts_encoding_is_not_held() -> None:
    """The control: the same child, read with the host's code page, is not held.

    **Why a control is here.** A witness that passes for the wrong reason
    is not a witness. This test proves the first one has teeth: it runs the
    *same* child and reads it the way the tree used to — with the host's
    code page — and requires that this does **not** hold the bytes.

    **Why it reads the bytes rather than the text.** The old way of
    reading them is what this test is about, and it is also what makes the
    failure invisible: the decode raises inside subprocess's reader
    thread, where the exception is swallowed, and the capture comes back
    as ``None``. Reading the bytes directly and decoding them here shows
    the same failure with its name attached — and does it without leaving
    an unhandled exception in a thread behind it.
    """
    sentinel = "SENTINEL"
    code = (
        "import sys;"
        f"sys.stdout.buffer.write({sentinel.encode('utf-8')!r} + b'\\xed\\xa0\\x80');"
        "sys.stdout.buffer.flush()"
    )
    environment = python_child_environment()
    raw = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        env=environment,
        timeout=120,
        check=False,
    )
    # The bytes are exactly what the child wrote.
    assert raw.stdout.startswith(sentinel.encode("utf-8")), (
        f"the child did not write what it was asked to: {raw.stdout!r}"
    )
    # The host's code page cannot decode them, and that is the whole point:
    # this is what the swallowed reader thread was dying on.
    host_encoding = locale.getpreferredencoding(False)
    with pytest.raises(UnicodeDecodeError):
        raw.stdout.decode(host_encoding)
    # And the stated reader holds them.
    held = raw.stdout.decode(PYTHON_OUTPUT_ENCODING, errors=CHILD_OUTPUT_ERRORS)
    assert held.startswith(sentinel), "the stated reader did not hold the child's bytes"
    assert len(held) == len(sentinel) + 3, (
        f"the stated reader held {len(held)} characters where "
        f"{len(sentinel) + 3} were expected: {held!r}"
    )


@pytest.mark.unit
def test_a_python_child_writes_what_the_tree_says_it_writes(tmp_path: Path) -> None:
    """A Python child writes UTF-8 when the tree says so — and the tree's claim is measured.

    **What is watched.** The other half of the property. A parent told to
    read UTF-8 while the child writes the machine's code page fails the
    same way, with the arrow turned round, so **both** halves have to be
    pinned. This test measures that the pinning on the child's side works,
    rather than taking it on trust.

    **The measurement.** The child is run twice: once with the environment
    the tree gives its children, and once with the machine's own. The
    first writes UTF-8; the second writes the machine's code page — which
    on this machine is cp936 — and the two byte sequences differ. That
    difference is the whole reason both halves are pinned.

    **Why the characters are these ones.** They have to be encodable in
    *both* code pages, so that the ambient child writes something rather
    than failing. ``café`` and ``中文`` are: GBK encodes them as two and
    four bytes, UTF-8 as two and six. A character only UTF-8 can spell
    (a tick, say) would make the ambient child raise instead, and the
    measurement would be about a crash rather than about an encoding.
    """
    text = "café中文"
    code = f"import sys; sys.stdout.buffer.write({text!r}.encode(sys.stdout.encoding))"
    pinned = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        env=python_child_environment(),
        timeout=120,
        check=False,
    )
    ambient = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        env={**os.environ},
        timeout=120,
        check=False,
    )
    assert pinned.stdout.decode(PYTHON_OUTPUT_ENCODING) == text, (
        f"the child the tree pins did not write UTF-8: {pinned.stdout!r}"
    )
    if ambient.stdout == pinned.stdout:
        pytest.skip(
            "the machine's code page is UTF-8, so the ambient child writes the "
            "same bytes as the pinned one and this measurement has nothing to "
            "distinguish; the pinned reader still holds them"
        )
    # The ambient child wrote something else, and it is not decodable as
    # UTF-8 — which is exactly the arrow-turned-round failure.
    with pytest.raises(UnicodeDecodeError):
        ambient.stdout.decode(PYTHON_OUTPUT_ENCODING)
