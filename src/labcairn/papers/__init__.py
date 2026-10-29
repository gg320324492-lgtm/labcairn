"""The mentor-trajectory line: a paper's versions and how they relate.

**What this package is.** LC-P2-08's application layer. It holds the
typed contracts for a manuscript, its versions, and the directed edges
between those versions.

**Why a new package and not a sub-package of `sources` or `evidence`.**
The two existing packages are about *material* and about *claims*, and a
version is neither: it is **a document's place in a history**, which
exists only when several documents are considered together. A `sources`
sub-package would make a version a kind of material and an `evidence`
sub-package would make it a kind of claim, and both would be wrong in a way
that is hard to undo later.

**What is here and what is not.** :mod:`labcairn.papers.versions` holds
the contracts and the refusals. The **alignment** — deciding which version
came from which, and refusing to decide when the evidence does not point
one way — is :mod:`labcairn.papers.alignment`, and the **feedback chain**
is LC-P2-09's.
"""

from labcairn.papers.versions import (
    EdgeSource,
    PaperProject,
    PaperVersion,
    StageCandidate,
    VersionEdge,
    VersionStatus,
)

__all__ = [
    "EdgeSource",
    "PaperProject",
    "PaperVersion",
    "StageCandidate",
    "VersionEdge",
    "VersionStatus",
]
