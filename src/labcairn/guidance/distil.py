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
from labcairn.guidance.rules import _rule_id, _validated_fields
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
    first_key, first = min(cases, key=lambda case: (case[0], case[1].comment_text))
    example = f"The advisor's comment ({first_key}): {first.comment_text}"
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
            rule_id=_rule_id(issue_type, statement, proposer, now),
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
