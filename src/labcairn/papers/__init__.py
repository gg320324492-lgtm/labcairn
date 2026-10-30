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
— a comment found in a manuscript, the change made in answer to it, the
judgement that the change answered the comment, and a later assessment of
the issue — is :mod:`labcairn.papers.feedback`,
:mod:`labcairn.papers.edits`, :mod:`labcairn.papers.responses` and
:mod:`labcairn.papers.assessments`.

**The chain's modules are not exported here on purpose.** They reach the
store, and the package's own import would then be a module that reaches
the store from outside the layer. The layer's guard
(``tests/test_application_layer.py``) names every module that does, and a
caller must be able to find each of them by its own name.
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
