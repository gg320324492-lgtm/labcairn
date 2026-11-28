"""The encodings this repository's children write in, stated once.

**Why this module exists.** A parent that reads a child's output with
``text=True`` and no ``encoding=`` decodes the bytes with the host's code
page. On this machine that is cp936 (GBK), and the failure is silent in the
worst way: the decode happens inside subprocess's reader thread, the
exception is swallowed there, and the capture comes back as ``None``. The
caller then fails on ``None.strip()`` — a message that says nothing about the
cause. That happened twice in one afternoon on 2026-11-28, and each time it
cost a whole-suite run.

**The property this module exists to serve.** *A child's bytes are decoded as
the encoding they were written in.* Both halves have to agree, and which
half is wrong depends on who writes the bytes:

* **``git``** writes its path and ref output as UTF-8, unconditionally. It
  converts from the wide-character filesystem itself, whatever the locale is.
  Measured on 2026-11-28: ``git rev-parse --show-toplevel`` in a directory
  whose name holds Chinese characters returns UTF-8 bytes, and those bytes
  raise ``UnicodeDecodeError`` under cp936. So ``GIT_OUTPUT_ENCODING`` is
  ``"utf-8"`` and it is a fact about git rather than a choice.
* **This repository's console script** forces UTF-8 on its own streams
  before it writes anything (``src/labcairn/cli/__init__.py``), so its
  output is UTF-8 by construction.
* **Any other Python program** writes in
  ``locale.getpreferredencoding(False)``, which is cp936 here — *unless*
  something says otherwise. Measured on 2026-11-28 with the project's own
  CPython 3.12: a plain child writes GBK; ``PYTHONIOENCODING=utf-8``,
  ``PYTHONUTF8=1`` and ``-X utf8`` each make it write UTF-8; and ``-I``
  (isolated mode) **ignores both environment variables**, so a child run with
  ``-I`` needs ``-X utf8`` on the command line.
* **A native tool** writes in whatever its own output code page is, which is
  the machine's business and not a fact this repository can assert.

**So a Python child needs both halves pinned**, and pinning only one turns
the failure around rather than fixing it: a parent told to read UTF-8 while
the child still writes the machine's code page fails the same way. That is
the "arrow turned round" case, and it is a real instance in this tree, not a
hypothetical.

**What the constants here are for.** They are the *names* of the answers, so
a call site reads as a statement about its child rather than as a bare
literal:

* :data:`GIT_OUTPUT_ENCODING` — git writes UTF-8.
* :data:`PYTHON_OUTPUT_ENCODING` — this repository's own children write
  UTF-8, and :func:`python_child_environment` is what makes them do it.
* :data:`CHILD_OUTPUT_ERRORS` — ``"replace"``, because a byte that is not
  decodable must cost the reader a wrong character and never a dead stream.
  A reader that cannot answer is worse than no reader.

This module holds no policy of its own: every constant here is a measured
fact about a particular child, and :mod:`tests.test_child_encodings` is the
witness that the tree's call sites agree with it.
"""

from __future__ import annotations

import os
from typing import Final

#: The encoding ``git`` writes its output in.
#:
#: UTF-8, unconditionally: git converts from the wide-character filesystem
#: itself, so its path and ref output does not depend on the machine's
#: locale. Measured on 2026-11-28 — ``git rev-parse --show-toplevel`` under
#: a directory named in Chinese returns UTF-8 bytes, which raise
#: ``UnicodeDecodeError`` under this machine's cp936.
GIT_OUTPUT_ENCODING: Final = "utf-8"

#: The encoding this repository's own children write their output in.
#:
#: UTF-8, because that is what the tree's output is: the console script
#: reconfigures its own streams to UTF-8 before it writes, and every script
#: and demonstration under ``scripts/`` and ``examples/`` is a Python
#: program whose stdout is read by this tree.
PYTHON_OUTPUT_ENCODING: Final = "utf-8"

#: The encoding a native tool writes its output in.
#:
#: **UTF-8, but only because the tool is told to.** A tool that ships with
#: the operating system writes in whatever output code page it was built
#: against, and that is not a fact this repository can assume — it is a fact
#: about the machine and the tool's build.
#:
#: Measured on 2026-11-28 with 7-Zip 26.02 on this machine: listing an
#: archive whose name holds Chinese characters writes the name as **GBK**
#: bytes, and those bytes raise ``UnicodeDecodeError`` under UTF-8. 7-Zip
#: has an output-charset switch (``-sccUTF-8``) and it makes the tool write
#: UTF-8 — so the tool is *asked* to write UTF-8, and the parent decodes
#: UTF-8. Pinning one half alone turns the failure around rather than
#: fixing it, and for a native tool that means passing the switch as well
#: as the ``encoding=``.
#:
#: The constant is named for the *kind* of child rather than for one tool, so
#: a reader sees that this is the native-tool case rather than a UTF-8
#: child that happens to be spelled differently.
NATIVE_OUTPUT_ENCODING: Final = "utf-8"

#: What a decode does with a byte it cannot represent.
#:
#: ``"replace"``: an undecodable byte costs the reader a wrong character and
#: never a dead stream. ``text=True`` without an ``encoding=`` raises inside
#: subprocess's reader thread, where the exception is swallowed, and the
#: capture comes back as ``None`` — so the failure a caller sees is
#: ``AttributeError: 'NoneType' object has no attribute 'strip'``, which
#: names neither the cause nor the fix.
CHILD_OUTPUT_ERRORS: Final = "replace"


def python_child_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """An environment in which a Python child writes UTF-8.

    **Both variables, because each covers what the other misses.**
    ``PYTHONIOENCODING`` sets the encoding of the standard streams, and
    ``PYTHONUTF8`` puts the interpreter itself in UTF-8 mode, which also
    covers the filesystem encoding and the text files the child opens. Either
    one alone leaves a gap.

    **The one that does not work is ``-I``.** Isolated mode ignores both
    environment variables, so a child run with ``-I`` has to be told on the
    command line — ``-X utf8`` — and the environment alone is not enough.
    Measured on 2026-11-28 with the project's own CPython 3.12.

    The rest of the environment is handed over unchanged, so that pinning
    those two takes nothing away from the child.
    """
    environment = dict(os.environ if base is None else base)
    environment["PYTHONIOENCODING"] = PYTHON_OUTPUT_ENCODING
    environment["PYTHONUTF8"] = "1"
    return environment
