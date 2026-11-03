"""Distilling a candidate rule from the chain's cases.

LC-P2-11 T01, the model's half. A distilled rule is a **model's
proposal**, and the record says so: its proposer is ``model_proposal``,
a name no person signs and no parameter can override. It lands in the
memory as a ``candidate`` — the same state a person's proposal lands in
— and **no amount of distilling moves it out**: only a second reader's
confirmation does, and the confirmer cannot be the proposer, so a model
cannot confirm its own work either (the second-reader rule of
2026-10-31, which names ``model_proposal`` a proposer like any other).

**And the distillation may not invent a scope** (the work order's T01):
the scope is the *applicability condition*, and a rule with a guessed
scope gets applied to papers it was never learned from. So this module
has **no scope parameter to invent one through**: the scope is
constructed from the cases — the anchored text each case's comment was
written against — and the example is the advisor's own words, with the
case's key beside them. A case that is not in the chain under the key
the caller names is refused: **a rule whose scope the cases do not
support is refused**, and so is a rule with no cases at all.

**And it may not misreport one.** A case whose comment the reader could
not place in the body carries no anchored text at all, and a scope that
quoted that empty string as the advisor's words would say the advisor
wrote about nothing — which is not what happened. So the scope names
every case it holds: the text the comment was written against, or the
fact that the reader could not place it, with the reason the chain
gives.

**And there is a second kind of case: a revision.** A mentor does not
always write in the margins. **A marked-up manuscript may hold hundreds
of tracked changes and not one comment**, and a distillation that reads
only comments has no case at all in such a manuscript — which is the
third pilot's shape (23 versions, 208 revisions, no comment), and the
reason this half of the module exists.

So :func:`distil_candidate_from_revisions` takes the same four fields
and reads its cases from the chain's tracked changes instead: the scope
is the paragraph each change sits in, **read in the change's own view**
(an insertion belongs to the accepted text, a deletion to the rejected
one), and the example is the reviewer's own edit.

**And the key is the product's on both paths.** A comment's issue key is
a person's judgement and is given (ADR-0017 C10); **a revision has no
such judgement to give** — a tracked change is a fact about a file, and
its address already names it. So the caller names the *revision* and the
product mints the key the case is filed under: **a caller cannot hand in
a key**, because a key a caller wrote would name material the chain may
not hold.

**And who proposes is said once, in the record.** The comment path's
proposer is ``model_proposal`` — a distillation run over a corpus of
comments is a model's work. **The revision path's proposer is
``operator_proposal``**, because an operator reading a mentor's tracked
changes and writing down what they add up to is a person's work, and
**the record must not claim a model did something a person did.** Both
land as a ``candidate``, and neither moves out of it without a second
reader's confirmation.

**The rows are reached through the application layer.** The chain's
comments come from :mod:`labcairn.application.chain` and the rule is
written through :mod:`labcairn.application.guidance`, so the distillation
reads no table of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Final

from labcairn.application import chain as chain_layer
from labcairn.application import guidance as guidance_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import guidance_refused
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.guidance.rules import _rule_id, _validated_fields, _write_rule_version_idempotent
from labcairn.papers.labels import ISSUE_LABELS

#: The proposer every distilled rule carries. **It is not a parameter**:
#: the distillation is a model's work, and the record is where that is
#: said once, in a place a caller cannot talk around.
MODEL_PROPOSER: Final[str] = "model_proposal"

#: The lead a scope carries when its cases name a text. **It is the
#: spelling the scope has always had**, so a scope built from cases that
#: all carry one reads exactly as it did before.
_SCOPE_LEAD: Final[str] = "Cases whose anchored text reads: "

#: The lead for the cases whose anchor resolved to no text. **A resolved
#: anchor and an unresolved one are two facts**, and the scope says which
#: is which rather than giving them the same words.
_EMPTY_ANCHOR_LEAD: Final[str] = "Cases whose anchor resolved to an empty text: "

#: The lead for the cases the reader could not place in the body.
_UNPLACED_LEAD: Final[str] = "Cases the reader could not place in the body: "

#: The lead a revision case's scope carries. **It is a different
#: sentence from the comment case's**, because a revision case is a
#: different thing: the change is the reviewer's own edit, and the
#: paragraph is where it was made.
_REVISION_SCOPE_LEAD: Final[str] = "Cases whose changed paragraph reads: "

#: The lead for a revision case whose paragraph could not be read. **The
#: empty string is never quoted as the reviewer's surroundings**, the
#: same way a comment's empty anchor is not quoted as the advisor's
#: words.
_REVISION_UNREAD_LEAD: Final[str] = "Cases whose changed paragraph could not be read: "

#: The proposer a **revision** distillation carries when the operator
#: distils the changes itself. **It is not the model**: a distillation
#: run over a corpus of comments is a model's work, and a person reading
#: a mentor's tracked changes and writing down what they add up to is a
#: person's work. **The record says which**, and the record is where that
#: is said once, in a place a caller cannot talk around.
OPERATOR_PROPOSER: Final[str] = "operator_proposal"


def _cases_of(
    context: ApplicationContext, issue_keys: Sequence[str]
) -> tuple[tuple[str, chain_layer.ChainComment], ...]:
    """The chain's events under the keys, each with its key, or the refusal.

    :raises ApplicationRefusedError: no key was given, or a key the chain
        holds no material under — the case a scope would be invented
        without.
    """
    keys = sorted({key for key in issue_keys if key.strip()})
    if not keys:
        raise guidance_refused(
            GuidanceRefusal.RULE_WITHOUT_SOURCE,
            "a distilled rule with no case behind it has nothing to scope it;"
            " name the chain material it was learned from",
        )
    by_key: dict[str, list[chain_layer.ChainComment]] = {}
    for comment in chain_layer.read_comments(context, issue_keys=keys):
        by_key.setdefault(comment.issue_key, []).append(comment)
    cases: list[tuple[str, chain_layer.ChainComment]] = []
    for key in keys:
        found = by_key.get(key, [])
        if not found:
            raise guidance_refused(
                GuidanceRefusal.RULE_WITHOUT_SOURCE,
                f"the chain holds no material under the key {key!r}, and a scope"
                " the cases do not support is a scope the cases did not give",
            )
        cases.extend((key, comment) for comment in found)
    return tuple(cases)


def _scope_of(cases: Sequence[tuple[str, chain_layer.ChainComment]]) -> str:
    """The applicability condition the cases give, and nothing more.

    **Every case is named, and a case is named by what it holds.** A case
    whose anchor resolved to a text names that text — the place the
    advisor's remark sits in the manuscript. A case whose anchor resolved
    to *no* text says so, and a case the reader could not place in the
    body says that, **with the reason the chain gives**.

    **The empty string is never quoted as the advisor's words.** A comment
    the reader could not place carries no anchored text, and quoting that
    as though it were a quotation of the manuscript would say the advisor
    wrote about nothing — which is not what happened: the reader could
    not find where the remark sits.

    **A resolved anchor and an unresolved one are two facts, and the scope
    keeps them apart.** A comment anchored on a point *is* placed — the
    reader found where it sits — and the text it covers is empty; a
    comment the reader could not place is not placed at all. The scope
    says *"resolved to an empty text"* for the first and *"could not
    place"* for the second, and never the same words for the two.

    **And the order is the cases' own.** The chain's rows come back in no
    particular order, so the cases are sorted here: a scope that changed
    shape between two distillations of the same comments would be a
    second spelling of one record.

    :param cases: each case with the key it is filed under.
    """
    ordered = sorted(cases, key=lambda case: (case[0], case[1].comment_text, case[1].feedback_id))
    quoted = sorted(
        {
            comment.anchor_text
            for _, comment in ordered
            if comment.anchor_status == "resolved" and comment.anchor_text
        }
    )
    empty = [
        (key, comment)
        for key, comment in ordered
        if comment.anchor_status == "resolved" and not comment.anchor_text
    ]
    unplaced = [(key, comment) for key, comment in ordered if comment.anchor_status != "resolved"]
    parts: list[str] = []
    if quoted:
        parts.append(_SCOPE_LEAD + "; ".join(f'"{text}"' for text in quoted))
    if empty:
        parts.append(
            _EMPTY_ANCHOR_LEAD + "; ".join(f"the comment under {key!r}" for key, _ in empty)
        )
    if unplaced:
        parts.append(
            _UNPLACED_LEAD
            + "; ".join(
                f"the comment under {key!r} ({comment.anchor_reason})" for key, comment in unplaced
            )
        )
    return ". ".join(parts)


def _comment_example_of(cases: Sequence[tuple[str, chain_layer.ChainComment]]) -> str:
    """The advisor's own words, with the case's key beside them.

    **The comment itself, not a description of it.** A comment is the
    advisor writing in the margin, and the words are the evidence; a rule
    whose example paraphrased them would be a rule illustrated by
    something the chain does not hold.

    **And the key is beside it, so the sentence traces back.** A reader
    must be able to open the case the example came from.

    **And the choice is stable.** The first case by key and then by text,
    so two distillations of the same comments show the same example — the
    same reason the scope is sorted.

    **Both comment doors read this one function.** A rule's first version
    and its next version are distilled from the same kind of case, and
    two spellings of one example would be two answers to what the case
    says.
    """
    first_key, first = min(cases, key=lambda case: (case[0], case[1].comment_text))
    return f"The advisor's comment ({first_key}): {first.comment_text}"


def distil_candidate(
    context: ApplicationContext,
    *,
    issue_type: str,
    statement: str,
    rule_context: str,
    issue_keys: Sequence[str],
    now: datetime,
) -> GuidanceRule:
    """Propose a rule *from cases*, as a candidate proposed by ``model_proposal``.

    **The scope and the example are the cases', not the model's.** The
    scope is assembled from the anchored text each case was written
    against — and, for a case the reader could not place in the body,
    from the fact that it could not place it and why. The example is the
    advisor's own comment, with the case's key beside it so the sentence
    traces back. The caller names the cases; the caller does not write the
    applicability condition.

    :raises ApplicationRefusedError: the problem is outside the closed
        vocabulary; the statement or its context is empty; no cases were
        named, or a named key the chain holds nothing under.
    """
    if issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    cases = _cases_of(context, issue_keys)
    scope = _scope_of(cases)
    example = _comment_example_of(cases)
    issue_type, statement, rule_context, scope, example, proposer, keys = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=MODEL_PROPOSER,
        sources=tuple(key for key, _ in cases),
    )
    return _write_rule_version_idempotent(
        context,
        guidance_layer.RuleDraft(
            rule_id=_rule_id(issue_type, statement, rule_context, scope, example, proposer, keys),
            version=1,
            issue_type=issue_type,
            statement=statement,
            rule_context=rule_context,
            scope=scope,
            example=example,
            proposed_by=proposer,
            sources=keys,
            proposed_at=now,
        ),
    )


def distil_comment_version_of(
    context: ApplicationContext,
    *,
    rule_id: str,
    issue_type: str,
    statement: str,
    rule_context: str,
    issue_keys: Sequence[str],
    now: datetime,
) -> GuidanceRule:
    """Write a **new version** of a rule, from comment cases, keeping its place.

    **The comment path needs the door the revision path already has.** A
    rule read once from comments is often a rule read from too little —
    a remark that says what to fix rather than how to recognise the fault
    — and a thin rule is fixed by writing it again, not by leaving a
    better one beside it. **A second rule under a new id would be two
    answers to one question**, and correcting the old row through
    :func:`labcairn.guidance.rules.supersede_rule` would hand-write the
    scope, which is the door a caller must not go around.

    **And the new version keeps the old one's place.** It is written under
    the same ``rule_id``, as the next version of it: the old version keeps
    the state it had, and the reader gets the newest words and nothing
    else.

    **And the scope and the example are the cases', not the caller's.**
    Exactly as on the first version — the scope is the anchored text each
    comment was written against, and the example is the advisor's own
    words with the case's key beside them — so **the caller cannot write
    a scope the cases do not support**.

    **And the proposer is the comment path's, as on the first version.**
    A distillation run over a corpus of comments is a model's work, and
    the record says so: this door carries ``model_proposal``, **not the
    revision path's ``operator_proposal``**, because the words were read
    from comments and no person sat between them and the rule. **The
    proposer belongs to the work, not to the id**: copying it from the
    old row would let one version's author stand for another's, which is
    the misreport the two proposer constants exist to prevent.

    **And the version starts as a candidate.** A rewording is not a
    confirmation: the new words need a second reader as much as the old
    ones did, and **the confirmer cannot be the proposer**, so the rule
    cannot be confirmed by the same hand that wrote it.

    **And a re-run is a new version, not the same row.** The version is a
    place in a sequence, not a function of the words, so running one
    correction twice writes the next version again — the same shape the
    revision door has. **The mint door's idempotency does not carry
    here**, and a caller that wants one row must not re-run its own
    correction.

    :raises ApplicationRefusedError: the rule is not there; the problem is
        outside the closed vocabulary; the statement or its context is
        empty; no comments were named, or a named key the chain holds
        nothing under.
    """
    if issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    # **The rule is read first**, so a rule that is not there is refused
    # before anything is written. The layer raises on its own.
    old = guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    cases = _cases_of(context, issue_keys)
    scope = _scope_of(cases)
    example = _comment_example_of(cases)
    issue_type, statement, rule_context, scope, example, proposer, keys = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=MODEL_PROPOSER,
        sources=tuple(key for key, _ in cases),
    )
    return guidance_layer.write_guidance_rule_version(
        context,
        guidance_layer.RuleDraft(
            rule_id=old.rule_id,
            version=old.version + 1,
            issue_type=issue_type,
            statement=statement,
            rule_context=rule_context,
            scope=scope,
            example=example,
            proposed_by=proposer,
            sources=keys,
            proposed_at=now,
        ),
    )


def _revision_cases_of(
    context: ApplicationContext, revision_event_ids: Sequence[str]
) -> tuple[chain_layer.ChainRevisionSource, ...]:
    """The revision cases the chain holds, each with the key it is filed under.

    **The caller names the revisions, and the key is the product's.** The
    caller cannot hand in a key: a key a caller wrote would name a case
    the chain may not hold, and the rule would be bound to material that
    does not exist. So the read mints the key from the revision event's
    own id, and the rule is bound to that.

    **A revision the chain holds no case for is refused, not skipped.** A
    rule that cites a case the chain cannot show is a rule whose scope
    the cases do not support — the same refusal the comment case raises,
    and for the same reason. **And a rule with no case at all is
    refused**: a rule without a source is not a rule.

    :raises ApplicationRefusedError: no revision was named, or a named
        revision the chain holds nothing under.
    """
    ids = tuple(dict.fromkeys(event_id for event_id in revision_event_ids if event_id.strip()))
    if not ids:
        raise guidance_refused(
            GuidanceRefusal.RULE_WITHOUT_SOURCE,
            "a distilled rule with no case behind it has nothing to scope it;"
            " name the revisions it was learned from",
        )
    found = {
        source.revision_event_id: source
        for source in chain_layer.read_revision_sources(context, revision_event_ids=ids)
    }
    cases: list[chain_layer.ChainRevisionSource] = []
    for event_id in ids:
        source = found.get(event_id)
        if source is None:
            raise guidance_refused(
                GuidanceRefusal.RULE_WITHOUT_SOURCE,
                f"the chain holds no revision under the id {event_id!r}, and a scope"
                " the cases do not support is a scope the cases did not give",
            )
        cases.append(source)
    return tuple(cases)


def _revision_scope_of(cases: Sequence[chain_layer.ChainRevisionSource]) -> str:
    """The applicability condition the revision cases give, and nothing more.

    **Every case is named, and a case is named by what it holds.** A case
    whose paragraph was read names that paragraph — the place the change
    was made in the manuscript. A case whose paragraph could not be read
    says so.

    **The empty string is never quoted as the reviewer's surroundings.**
    A change whose paragraph could not be read carries no context, and
    quoting that as though it were the manuscript would say the reviewer
    changed something in a paragraph that does not exist — which is not
    what happened.

    **And the order is the cases' own.** The chain's rows come back in no
    particular order, so the cases are sorted here: a scope that changed
    shape between two distillations of the same revisions would be a
    second spelling of one record.
    """
    ordered = sorted(cases, key=lambda case: (case.source_key, case.revision_event_id))
    quoted = sorted({case.paragraph_text for case in ordered if case.paragraph_text})
    unread = [case for case in ordered if not case.paragraph_text]
    parts: list[str] = []
    if quoted:
        parts.append(_REVISION_SCOPE_LEAD + "; ".join(f'"{text}"' for text in quoted))
    if unread:
        parts.append(
            _REVISION_UNREAD_LEAD
            + "; ".join(f"the revision under {case.source_key!r}" for case in unread)
        )
    return ". ".join(parts)


def _revision_example_of(cases: Sequence[chain_layer.ChainRevisionSource]) -> str:
    """The reviewer's own change, with the case's key beside it.

    **The change's own words, not a description of them.** A revision is
    the reviewer editing the manuscript, and the edit is the evidence; a
    rule whose example paraphrased it would be a rule illustrated by
    something the chain does not hold.

    **And the key is beside it, so the sentence traces back.** The same
    rule the comment case follows — a reader must be able to open the
    case the example came from.

    **And the example is the case that shows the change best.** A tracked
    change is often **a fragment of a sentence** — Word records the half
    a writer typed at one moment and the other half at another — and the
    first case by key order may be the half that says least. **So the
    example is the longest change among the cases**, because the longest
    is the one that shows what the reviewer wrote; and the tie is broken
    by the key, so the choice is the same on every machine.

    **And an insertion is shown before a deletion, whatever their
    lengths.** A rule says what a manuscript *should* carry, so its
    example has to be the words the reviewer wrote — **a deletion shows
    what the reviewer took away**, and a rule illustrated by the thing it
    tells a reader not to do is illustrated by its own counterexample.
    This is not hypothetical: a mentor replacing one mechanism with
    another deletes a phrase longer than the one they insert, and a reader
    that picked by length alone would show the phrase the mentor rejected.
    """
    first = max(
        cases,
        key=lambda case: (
            case.kind == "ins",
            len(case.text),
            case.source_key,
            case.revision_event_id,
        ),
    )
    if first.change_kind == "with_text":
        what = first.text
    elif first.kind == "ins":
        what = f"an insertion of {first.text!r}"
    elif first.kind == "del":
        what = f"a deletion of {first.text!r}"
    else:
        what = f"a change of kind {first.kind!r}"
    return f"The reviewer's change ({first.source_key}): {what}"


def distil_candidate_from_revisions(
    context: ApplicationContext,
    *,
    issue_type: str,
    statement: str,
    rule_context: str,
    revision_event_ids: Sequence[str],
    now: datetime,
) -> GuidanceRule:
    """Propose a rule *from revision cases*, as a candidate proposed by ``operator_proposal``.

    **The second way a case reaches a rule, and it exists because a
    mentor does not always write in the margins.** A marked-up manuscript
    may hold hundreds of tracked changes and no comment at all, and a
    rule distilled only from comments has **no case at all** in such a
    manuscript. So the cases here are the changes themselves: the
    reviewer's own edits, each with the paragraph it was made in.

    **The scope and the example are the cases', not the caller's.** The
    scope is assembled from the paragraph each change sits in — read in
    the change's own view, so an insertion is quoted from the accepted
    text and a deletion from the rejected one — and the example is the
    reviewer's own change, with the case's key beside it.

    **The key is the product's, and the caller cannot write one.** The
    caller names the revisions; the product mints the key each case is
    filed under. **A key a caller wrote would name a case the chain may
    not hold**, and a rule bound to material that does not exist is not
    a rule.

    **And who proposes is said once, in the record.** The proposer here
    is ``operator_proposal``, **not** ``model_proposal``: a distillation
    run over a corpus of comments is a model's work, while an operator
    reading a mentor's tracked changes and writing down what they add up
    to is a person's work, and **the record must not claim a model did
    something a person did.** The candidate is still a candidate: only a
    second reader confirms it, and the confirmer cannot be the proposer.

    :raises ApplicationRefusedError: the problem is outside the closed
        vocabulary; the statement or its context is empty; no revisions
        were named, or a named revision the chain holds nothing under.
    """
    if issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    cases = _revision_cases_of(context, revision_event_ids)
    scope = _revision_scope_of(cases)
    example = _revision_example_of(cases)
    issue_type, statement, rule_context, scope, example, proposer, keys = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=OPERATOR_PROPOSER,
        sources=tuple(case.source_key for case in cases),
    )
    return _write_rule_version_idempotent(
        context,
        guidance_layer.RuleDraft(
            rule_id=_rule_id(issue_type, statement, rule_context, scope, example, proposer, keys),
            version=1,
            issue_type=issue_type,
            statement=statement,
            rule_context=rule_context,
            scope=scope,
            example=example,
            proposed_by=proposer,
            sources=keys,
            proposed_at=now,
        ),
    )


def distil_revision_version_of(
    context: ApplicationContext,
    *,
    rule_id: str,
    issue_type: str,
    statement: str,
    rule_context: str,
    revision_event_ids: Sequence[str],
    now: datetime,
) -> GuidanceRule:
    """Write a **new version** of a rule, from revision cases, keeping its place.

    **The third way a rule is written, and it exists because a rule read
    once is often a rule read from too little.** A distillation run over a
    mentor's tracked changes may split one edit into its fragments and
    write a rule about a fragment — a statement that describes what a rule
    should say rather than a standard a reader could apply. **The rule is
    then not wrong; it is thin**, and a thin rule is fixed by writing it
    again, not by leaving it beside a better one.

    **And the new version keeps the old one's place.** A new rule under a
    new id would be a second rule about the same thing, and the memory
    would hold two answers to one question — **a rule that outlives its
    work is a second place to look for the same code.** So the version is
    written under the same ``rule_id``, as the next version of it: **the
    old version keeps the state it had**, and the reader gets the newest
    words and nothing else.

    **And the scope and the example are the cases', not the caller's.**
    Exactly as on the first version — the scope is the paragraph each
    change sits in, and the example is the reviewer's own change — so
    **the caller cannot write a scope the cases do not support**, and a
    caller that had to hand-write one would have had to go around the
    product to do it.

    **And the proposer is the operator's, as on the first version.** A
    person read the mentor's tracked changes and wrote down what they add
    up to, and the record says so where a caller cannot talk around it.

    **And the version starts as a candidate.** A rewording is not a
    confirmation: the new words need a second reader as much as the old
    ones did, and **the confirmer cannot be the proposer**, so the rule
    cannot be confirmed by the same hand that wrote it.

    :raises ApplicationRefusedError: the rule is not there; the problem is
        outside the closed vocabulary; the statement or its context is
        empty; no revisions were named, or a named revision the chain holds
        nothing under.
    """
    if issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    # **The rule is read first**, so a rule that is not there is refused
    # before anything is written. The layer raises on its own.
    old = guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    cases = _revision_cases_of(context, revision_event_ids)
    scope = _revision_scope_of(cases)
    example = _revision_example_of(cases)
    issue_type, statement, rule_context, scope, example, proposer, keys = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=OPERATOR_PROPOSER,
        sources=tuple(case.source_key for case in cases),
    )
    return guidance_layer.write_guidance_rule_version(
        context,
        guidance_layer.RuleDraft(
            rule_id=old.rule_id,
            version=old.version + 1,
            issue_type=issue_type,
            statement=statement,
            rule_context=rule_context,
            scope=scope,
            example=example,
            proposed_by=proposer,
            sources=keys,
            proposed_at=now,
        ),
    )
