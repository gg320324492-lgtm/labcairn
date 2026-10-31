"""The retrieval over the guidance memory: a query in, sourced rules out.

LC-P2-11 T02 and T03. The memory answers with **rules that carry their
sources and their cases**, never a bare sentence: every hit resolves the
rule's chain material against the chain's *current* state at the moment of
the query, because a rule whose source no longer stands is not a rule a
card can cite — **an expired thing is judged by its state, not by the
clock**, which is the lesson LC-P2-10's review wrote down and this module
carries into the memory.

**The reader's permission decides which sources stand for them.** Each
source resolves to the material its feedback events were written against,
and that material goes through the permission layer like any other read —
:func:`~labcairn.application.consent.evaluate_each`, whose denied
resources are *dropped* rather than refused (ADR-0003 C5), so **a rule
whose source is out of the reader's reach does not come back**, and a
rule with two sources stands on the one they may read.

**What the retrieval does not do.** It does not resolve conflicts — two
rules that disagree are both returned, and neither wins by being newer
(the ordering never looks at a version or a timestamp, only at the state
a person put the rule in and the rule's own identity). It does not invent
relevance scores; the query is an issue type and free text, the match is
exactness on the one and containment on the other, and **a miss is an
empty answer, not a refusal** — saying what was not found is LC-P2-12's
honesty to deliver, and this module's honesty is to return nothing rather
than something nearest.

**And a withdrawal is not silent.** A rule whose sources have all stopped
standing is not served — and it is not *disappeared* either:
:func:`invalidated_rules` reports it, with the reason each dead source
gives, because the record of what was withdrawn is itself a record.

**The rows are reached through the application layer.** The memory's rules
come from :mod:`labcairn.application.guidance` and the chain's facts from
:mod:`labcairn.application.chain`, so the retrieval reads no table of its
own — and the permission layer is asked here, where the material is named.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

from labcairn.application import chain as chain_layer
from labcairn.application import consent
from labcairn.application import guidance as guidance_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import guidance_refused
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.papers.feedback import MAX_MANUSCRIPT_BYTES
from labcairn.papers.labels import ISSUE_LABELS
from labcairn.security.capabilities import CapabilityId

#: The response states a rule's source may stand in. A source whose
#: judgement says the change did not answer the comment is material that
#: no longer supports the rule — *withdrawn from under the rule* is a
#: fact about the chain's rows, not a field on the rule.
LIVING_STATES: Final[frozenset[str]] = frozenset({"addressed", "partially_addressed"})

#: The default result size. The memory is small — a person's rules, not
#: a corpus — and the ceiling exists so a query nobody narrowed cannot
#: stream the whole library into a card.
DEFAULT_LIMIT: Final[int] = 20


@dataclass(frozen=True)
class SourceState:
    """One source of a rule, resolved against the chain at query time.

    **Three facts, and each explains one way a source dies**: the chain
    holds no material under the key (:attr:`found`), the material is out
    of the reader's reach (:attr:`reachable`), or a judgement on it says
    the change did not answer the comment (:attr:`addressed`).
    """

    issue_key: str
    #: The chain holds feedback events under this key.
    found: bool
    #: The policy permits reading the material those events were written
    #: against. Checked per reader, at query time.
    reachable: bool
    #: A judgement on that material says the change answered the comment.
    addressed: bool


@dataclass(frozen=True)
class RuleHit:
    """A rule the memory serves, with the states its sources stand in.

    **The counterexamples are already inside** — :class:`GuidanceRule`
    carries them from the same read — **and the caller cannot drop
    them**: a rule served without its cases is the unconditional serving
    the work order refuses.
    """

    rule: GuidanceRule
    #: The rule's sources, as the chain stands now. A source that no
    #: longer stands has been dropped from this tuple; a rule with none
    #: left is not returned at all.
    sources: tuple[SourceState, ...]


@dataclass(frozen=True)
class InvalidatedRule:
    """A rule the memory has stopped serving, and the reasons it stopped.

    **The invalidation is not silent** — this is the report T03 asks for.
    A rule lands here when none of its sources stand any more; the
    reasons are the source states that killed it, each naming its own
    way of dying.
    """

    rule: GuidanceRule
    #: The sources that do not stand, and why.
    reasons: tuple[SourceState, ...]


def _reachable_materials(
    context: ApplicationContext, version_ids: tuple[str, ...]
) -> frozenset[str]:
    """The versions whose material the reader may read, as the policy says.

    **The permission layer is asked, not bypassed** — the same
    :func:`~labcairn.application.consent.evaluate_each` a bulk listing
    goes through, so a denied material is dropped and the rule it
    supported goes quiet for this reader without anybody's refusal.
    """
    paths = chain_layer.read_material_paths(context, version_ids=version_ids)
    if not paths:
        return frozenset()
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_MANUSCRIPT_BYTES},
        resources=tuple(context.resource_for(path) for path in paths.values()),
    )
    return frozenset(resource.declared_key for resource in permitted)


def _living_sources(
    context: ApplicationContext, issue_keys: tuple[str, ...]
) -> tuple[SourceState, ...]:
    """Resolve the rule's sources against the chain, as the chain stands now.

    **A source lives when the material is there, the reader may read it,
    and a judgement on it says the change answered the comment.** A key
    nobody bound a feedback event to is material the memory claims to
    have learned from and the chain cannot show — it does not live. A key
    whose material the policy denies is a source this reader cannot
    check, and the memory does not serve what it cannot show. A key whose
    judgement says ``not_addressed`` is material withdrawn from under the
    rule, and a re-judgement — the row's state, changed — brings it back
    without the memory being touched at all.
    """
    living: list[SourceState] = []
    for key in issue_keys:
        comments = chain_layer.read_comments(context, issue_keys=(key,))
        if not comments:
            living.append(SourceState(issue_key=key, found=False, reachable=False, addressed=False))
            continue
        feedback_ids = tuple(comment.feedback_id for comment in comments)
        version_ids = tuple({comment.version_id for comment in comments})
        reachable = _reachable_materials(context, version_ids)
        stands = bool(reachable)
        states = chain_layer.read_response_states(context, feedback_ids=feedback_ids)
        addressed = any(state in LIVING_STATES for state in states)
        living.append(SourceState(issue_key=key, found=True, reachable=stands, addressed=addressed))
    return tuple(living)


def _standing(sources: tuple[SourceState, ...]) -> tuple[SourceState, ...]:
    """The sources that live: found, reachable, and judged answered."""
    return tuple(
        source for source in sources if source.found and source.reachable and source.addressed
    )


def _resolvable_rules(
    rules: tuple[GuidanceRule, ...], *, issue_type: str | None, needle: str, states: tuple[str, ...]
) -> Iterator[GuidanceRule]:
    """The latest-version rules a query could possibly be about."""
    for rule in rules:
        if rule.state not in states:
            continue
        if issue_type is not None and rule.issue_type != issue_type:
            continue
        if needle and not any(
            needle in (column or "")
            for column in (rule.statement, rule.context, rule.scope, rule.example)
        ):
            continue
        yield rule


def search_rules(
    context: ApplicationContext,
    *,
    issue_type: str | None = None,
    query: str | None = None,
    include_candidates: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> tuple[RuleHit, ...]:
    """The confirmed rules that match, with their sources and their cases.

    **The default serves what a card may cite**: confirmed rules, and
    disputed ones with the reason they are disputed travelling in the
    rule itself. **A candidate is not served** unless the caller says so
    explicitly — a proposal reaching a card would be a proposal dressed
    as a record (ADR-0016 D8), and role C reviewing a candidate passes
    ``include_candidates`` for that, and only that.

    **A candidate is shown to its reviewer on the cases that exist; a
    confirmed rule stands only on the sources that were answered.** A
    proposal's cases have usually not been judged at all — nobody has
    answered the comment yet — so requiring a judgement to show the
    proposal would hide from the reviewer the very thing they are to
    judge. The state conditions split: a candidate's sources must be
    found and in the reader's reach, a confirmed or disputed rule's
    must also carry a judgement that says the change answered.

    **The ordering never consults time.** Confirmed before everything
    else, and within a state by the rule's own id — a stable order that
    cannot make the newest rule win a disagreement by being newest,
    which is what the work order refuses.

    The text match is containment, case-sensitively, over the rule's
    statement, context, scope and example. A limit below one asks for
    nothing and gets nothing; the ceiling is honoured *after* the
    ordering, so the hits cut are the ones the order ranked last and not
    whichever came off the table first.

    :raises ApplicationRefusedError: an issue type outside the closed
        vocabulary was asked for.
    """
    if issue_type is not None and issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    states = (
        ("candidate", "confirmed", "disputed")
        if include_candidates
        else (
            "confirmed",
            "disputed",
        )
    )
    needle = query.strip() if query else ""
    hits: list[RuleHit] = []
    rules = guidance_layer.read_guidance_rules(context)
    for rule in _resolvable_rules(rules, issue_type=issue_type, needle=needle, states=states):
        sources = _living_sources(context, rule.sources)
        standing = tuple(
            source
            for source in sources
            if source.found and source.reachable and (source.addressed or rule.state == "candidate")
        )
        if not standing:
            continue
        hits.append(RuleHit(rule=rule, sources=standing))
    ordered = sorted(hits, key=lambda hit: (hit.rule.state != "confirmed", hit.rule.rule_id))
    return tuple(ordered[:limit]) if limit >= 1 else ()


def invalidated_rules(
    context: ApplicationContext,
    *,
    issue_type: str | None = None,
    query: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[InvalidatedRule, ...]:
    """The rules the memory has stopped serving, and the reasons it stopped.

    **The invalidation is not silent** (LC-P2-11 T03): a rule whose
    sources have all stopped standing is out of :func:`search_rules`'s
    answer, and it is *here* — each dead source saying which of the
    three ways it died. A rule with one living source is not here, even
    with its others dead: it is still served, on the sources that stand.

    The same filters apply as to :func:`search_rules`, minus the
    candidates — a candidate was never served, so it cannot be
    invalidated; it is simply awaiting its second reader.
    """
    if issue_type is not None and issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    needle = query.strip() if query else ""
    invalidations: list[InvalidatedRule] = []
    rules = guidance_layer.read_guidance_rules(context)
    for rule in _resolvable_rules(
        rules,
        issue_type=issue_type,
        needle=needle,
        states=("confirmed", "disputed"),
    ):
        sources = _living_sources(context, rule.sources)
        standing = _standing(sources)
        if standing:
            continue
        invalidations.append(InvalidatedRule(rule=rule, reasons=sources))
    ordered = sorted(
        invalidations, key=lambda item: (item.rule.state != "confirmed", item.rule.rule_id)
    )
    return tuple(ordered[:limit]) if limit >= 1 else ()
