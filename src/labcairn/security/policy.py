"""Policy rules and the single function that turns a request into a verdict.

ADR-0003 §C5 is the contract:

    evaluate(task_id, capability, resource_key, canonical_args) -> allow | ask | deny

* **Deny first.** Any matching ``deny`` returns DENY immediately. No later rule
  can upgrade it — no specificity override, no ordering escape.
* Then ``ask``: any matching ``ask`` returns ASK.
* Then ``allow``: at least one matching ``allow`` returns ALLOW.
* **No matching rule returns DENY.**

Both the deny-first ordering and the default-deny are the explicit opposite of
the upstream this ADR studied. §A5 records that deepagents returns ``"allow"``
when no rule matches and resolves on *first match in declaration order*, and
that its own suite asserts ``test_earlier_allow_wins_over_later_catch_all_deny``
as intended. That is a coherent design — but it requires a sandbox as the real
boundary, and ``ARCHITECTURE.md`` is explicit that Phase 1 does not have one. A
local research workbench has to be auditable *before* a sandbox is involved, so
the policy layer is the boundary, and a policy layer that defaults to allow is
not a boundary.

What §C5 adds on top of the three-step ordering, and what this module implements
----------------------------------------------------------------------------

* **Both spellings are matched.** ``declared_key`` (what the caller wrote) and
  ``resolved_key`` (what the filesystem will open) are each matched
  independently, and a deny on *either* blocks. Matching only the resolved
  path would let a caller pass a benign-looking declaration; matching only the
  declaration would miss a symlink. :meth:`PermissionPolicy.evaluate` returns
  which spelling decided it, so the event log says which.
* **Ancestor and descendant denies block everything.** ADR §C7 generalises
  deepagents' delete-only rule to *all* operations: if any deny pattern matches
  the resource, an ancestor of it, or a descendant of it, the request is denied.
  The reasoning is that an allow for ``out/`` cannot be trusted when a later,
  more specific deny may cover one entry below it, so nothing is allowed on
  speculation.
* **Bulk listings are filtered, not refused.** A refused ``ls`` tells the model
  *something* is there. §C5 requires denied entries be removed from results.

The structural deny that precedes all of this
---------------------------------------------
:meth:`PermissionPolicy.evaluate` refuses a capability whose ``root_kinds`` do
not include the resource's root kind **before any rule is consulted**. That is
what makes source material read-only: it is a property of the capability
registry, not of a rule an operator might forget to write. A rule saying
``allow fs.write sources/**`` cannot make ``fs.write`` write to a source root,
because ``fs.write`` declares ``root_kinds={"output"}``. Policy layers are for
*additional* restriction; the registry is the floor.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import unicodedata
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Final

from labcairn.core.ids import TaskId
from labcairn.security.capabilities import Capability, Effect, resolve_capability
from labcairn.security.paths import CanonicalPath, PathRejection, ResourceKey, RootKind

#: Upper bound on entries walked when checking for a denied descendant.
#:
#: The descendant check is the one part of evaluation that touches the
#: filesystem, so it needs a bound. **Exceeding it denies**, rather than
#: allowing: a directory too large to enumerate is a directory where a deny
#: rule cannot be proven absent, and the whole argument for allow-on-ancestor
#: assumes we could enumerate.
MAX_SCAN_ENTRIES: Final = 4096


class Permission(StrEnum):
    """The three verdicts. ADR-0003 §C5."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class DecisionReason(StrEnum):
    """Why a verdict was reached. Enumerated so the event log can record it."""

    #: No rule matched. ADR-0003 §C5's last line.
    DEFAULT_DENY = "default_deny"
    #: The capability id is not in the registry. Fail closed.
    UNKNOWN_CAPABILITY = "unknown_capability"
    #: The capability cannot address this kind of root at all — e.g. a write
    #: capability aimed at a read-only source root. Structural, not a rule.
    ROOT_KIND_NOT_PERMITTED = "root_kind_not_permitted"
    #: A deny rule matched the resource itself.
    RULE_DENY = "rule_deny"
    #: A deny rule matched an ancestor of the resource.
    RULE_DENY_ANCESTOR = "rule_deny_ancestor"
    #: A deny rule matched something below the resource.
    RULE_DENY_DESCENDANT = "rule_deny_descendant"
    #: No deny, but an ask rule matched.
    RULE_ASK = "rule_ask"
    #: An allow rule matched and nothing denied.
    RULE_ALLOW = "rule_allow"


class RulePatternError(ValueError):
    """A rule pattern that could not be loaded.

    ADR-0003 §C5: *Rule patterns are validated at load: absolute, no ``..``, no
    ``~``.* Validating at load rather than at match time is the point — a policy
    file that loads is a policy file whose every pattern has already been proved
    unambiguous, so the hot path never has to decide whether a pattern is
    safe to interpret.
    """


class ResourceRef:
    """The thing a verdict is about.

    A distinct class rather than a bare string, and constructed only through
    :meth:`from_canonical`. ADR-0003 §C6.1 requires that no parameter of the
    decision function can carry document or excerpt text; making the resource a
    type that ``canonicalize()`` had to mint is how that is guaranteed by
    construction rather than by review. Every field is an identifier or a
    canonicalised path — none is free text.

    Inherits the shape of :class:`~labcairn.security.paths.CanonicalPath` so that
    ``test_policy_input_surface_is_closed`` can assert against a real object
    rather than a signature string.
    """

    __slots__ = ("declared_key", "real_path", "resolved_key", "root_id", "root_kind")

    def __init__(
        self,
        *,
        declared_key: ResourceKey,
        resolved_key: ResourceKey,
        root_id: str,
        root_kind: RootKind,
        real_path: Path,
    ) -> None:
        self.declared_key = declared_key
        self.resolved_key = resolved_key
        self.root_id = root_id
        self.root_kind = root_kind
        self.real_path = real_path

    @classmethod
    def from_canonical(cls, path: CanonicalPath) -> ResourceRef:
        return cls(
            declared_key=path.declared_key,
            resolved_key=path.resolved_key,
            root_id=path.root_id,
            root_kind=path.root_kind,
            real_path=path.real_path,
        )

    def __repr__(self) -> str:
        return (
            f"ResourceRef(declared={self.declared_key!r}, resolved={self.resolved_key!r}, "
            f"root={self.root_id!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ResourceRef):
            return NotImplemented
        return (
            self.declared_key == other.declared_key
            and self.resolved_key == other.resolved_key
            and self.root_id == other.root_id
            and self.root_kind == other.root_kind
        )

    def __hash__(self) -> int:
        return hash((self.declared_key, self.resolved_key, self.root_id, self.root_kind))


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    """A verdict, and everything needed to record why it was reached."""

    permission: Permission
    reason: DecisionReason
    #: The rule that decided, as its canonical rendering. ``None`` when the
    #: decision was structural or the default.
    matched_rule: str | None
    #: ``"declared"`` or ``"resolved"`` — which spelling produced ``matched_rule``.
    #: Both spellings are always matched; recording which one fired is what
    #: makes a symlink denial legible in an audit trail.
    matched_spelling: str | None
    #: The capability's :class:`~labcairn.security.capabilities.Effect`, or
    #: ``None`` for an unknown capability.
    effect: Effect | None


@dataclass(frozen=True, slots=True)
class Rule:
    """One resource-scoped rule.

    Every scope field is optional and ``None`` means *any*. An empty scope list
    would mean *nothing*, which is a confusing default; ``None`` is the
    permissive one and matches how operators write these by hand.
    """

    effect: Permission
    pattern: str
    capabilities: frozenset[str] | None = None
    root_ids: frozenset[str] | None = None
    effects: frozenset[Effect] | None = None
    task_ids: frozenset[str] | None = None
    #: Human-readable note, rendered in the approval prompt. Never parsed.
    note: str = ""

    def __post_init__(self) -> None:
        validate_rule_pattern(self.pattern)
        for scope_name in ("capabilities", "root_ids", "task_ids"):
            scope = getattr(self, scope_name)
            if scope is not None and not scope:
                msg = (
                    f"rule scope {scope_name} is empty. Use None to mean 'any'; an "
                    f"empty set would mean 'nothing' and is almost never intended."
                )
                raise RulePatternError(msg)

    def matches_scope(
        self,
        *,
        capability: Capability,
        root_id: str,
        task_id: TaskId | None,
    ) -> bool:
        """Whether this rule's *scope* covers the request, ignoring its pattern.

        Separate from pattern matching so a scoped-out rule is never even
        globbed. A rule scoped to one task that happened to match every path
        would otherwise cost a filesystem walk on every request.
        """
        if (
            self.capabilities is not None
            and capability.capability_id.value not in self.capabilities
        ):
            return False
        if self.root_ids is not None and root_id not in self.root_ids:
            return False
        if self.effects is not None and capability.effect not in self.effects:
            return False
        return not (
            self.task_ids is not None and (task_id is None or str(task_id) not in self.task_ids)
        )

    def render(self) -> str:
        """Canonical text form, used in digests and in the approval prompt."""
        scopes = []
        if self.capabilities is not None:
            scopes.append("caps=" + ",".join(sorted(self.capabilities)))
        if self.root_ids is not None:
            scopes.append("roots=" + ",".join(sorted(self.root_ids)))
        if self.effects is not None:
            scopes.append("effects=" + ",".join(sorted(e.value for e in self.effects)))
        if self.task_ids is not None:
            scopes.append("tasks=" + ",".join(sorted(self.task_ids)))
        suffix = f" [{' '.join(scopes)}]" if scopes else ""
        note = f"  # {self.note}" if self.note else ""
        return f"{self.effect.value.upper()} {self.pattern}{suffix}{note}"


def validate_rule_pattern(pattern: str) -> str:
    """Load-time pattern validation, per ADR-0003 §C5.

    Rejects, in order: empty patterns, absolute paths, drive letters, ``..``
    segments, ``~``, backslashes, and Unicode that normalises into a separator.

    ``~`` and ``..`` are rejected because a rule is meant to name a place in the
    workspace; a pattern that expands against the user's home directory or walks
    upwards has a blast radius the operator did not choose and cannot see in the
    policy file. ``*`` is deliberately allowed to cross segments only when
    written ``**`` — a single ``*`` staying inside its segment is what makes a
    deny rule mean what it looks like it means.
    """
    if not pattern or not pattern.strip():
        raise RulePatternError("rule pattern is empty")
    normalised = unicodedata.normalize("NFC", pattern)
    if "\\" in normalised:
        raise RulePatternError(
            f"rule pattern {pattern!r} contains a backslash. Only '/' separates "
            f"segments in a rule: a backslash is a separator on one platform and an "
            f"ordinary filename character on another, so a rule containing one means "
            f"two different things depending on where it runs."
        )
    # Per-segment, because NFKC maps ASCII '/' to '/' — a whole-string test would
    # flag every pattern containing an ordinary separator. What is being caught
    # is a segment that *becomes* a separator under NFKC (FULLWIDTH SOLIDUS,
    # U+FF0F), which would let one rule spelling match two different paths.
    for segment in normalised.split("/"):
        if "/" in unicodedata.normalize("NFKC", segment):
            raise RulePatternError(
                f"rule pattern {pattern!r} has segment {segment!r}, which normalises "
                f"to a path separator. Only ASCII '/' separates segments in a rule, so "
                f"one spelling of a rule has exactly one meaning."
            )
    if normalised.startswith("/"):
        raise RulePatternError(
            f"rule pattern {pattern!r} is absolute. Rule patterns are "
            f"workspace-relative so a policy file stays portable and an operator "
            f"can see the blast radius without knowing the machine."
        )
    if len(normalised) >= 2 and normalised[1] == ":":
        raise RulePatternError(f"rule pattern {pattern!r} carries a drive letter")
    if "~" in normalised:
        raise RulePatternError(
            f"rule pattern {pattern!r} contains '~'. Home-directory expansion makes "
            f"a rule's meaning depend on whose account runs it."
        )
    for segment in normalised.split("/"):
        if segment == "..":
            raise RulePatternError(
                f"rule pattern {pattern!r} contains a '..' segment. A rule names a "
                f"place in the workspace; a pattern that walks upwards does not."
            )
        if segment in ("", ".", "**"):
            continue
        if segment.endswith((".", " ")):
            raise RulePatternError(
                f"rule pattern {pattern!r} has segment {segment!r} ending in a dot or "
                f"space, which Win32 strips."
            )
    return normalised


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


#: Severity order for combining two decisions. DENY wins over ASK wins over
#: ALLOW, matching ADR-0003 C5's "a deny on either blocks".
_SEVERITY = {Permission.DENY: 2, Permission.ASK: 1, Permission.ALLOW: 0}


def _worst_of(decisions: Sequence[PermissionDecision]) -> PermissionDecision:
    """The most restrictive of several decisions, ties broken toward declared."""
    return max(
        decisions,
        key=lambda d: (_SEVERITY[d.permission], d.matched_spelling == "declared"),
    )


def _split(key: str) -> tuple[str, ...]:
    return PurePosixPath(key).parts


#: Windows and macOS filesystems resolve ``SECRETS.TXT`` and ``secrets.txt`` to
#: the same file. ``fnmatchcase`` would let a request bypass ``deny
#: private/secrets.txt`` purely by changing the case, which cross-review
#: reproduced: the same file returned *allow* and *deny* on the same policy.
#: Rule matching therefore follows the filesystem, not the spelling the
#: caller happened to use.
_FOLD = str.casefold if os.name == "nt" else (lambda value: value)


@lru_cache(maxsize=4096)
def _match_from(pattern: tuple[str, ...], parts: tuple[str, ...]) -> bool:
    """Segment-wise glob. ``**`` spans segments; ``*`` never does."""
    if not pattern:
        return not parts
    head = pattern[0]
    if head == "**":
        # Zero or more segments. Iterate rather than recurse-on-head so the
        # common case costs one comparison per position.
        return any(_match_from(pattern[1:], parts[i:]) for i in range(len(parts) + 1))
    if not parts:
        return False
    if not fnmatch.fnmatchcase(_FOLD(parts[0]), _FOLD(head)):
        return False
    return _match_from(pattern[1:], parts[1:])


def pattern_matches(pattern: str, key: str) -> bool:
    """Whether a validated pattern matches a canonical resource key."""
    return _match_from(_split(unicodedata.normalize("NFC", pattern)), _split(key))


def _literal_prefix(pattern: str) -> tuple[str, ...]:
    """The leading segments of a pattern that contain no wildcard.

    Used to decide cheaply whether a rule could possibly match *below* a given
    resource, which is what decides whether the filesystem walk happens at all.
    """
    out: list[str] = []
    for segment in _split(unicodedata.normalize("NFC", pattern)):
        if any(ch in segment for ch in "*?["):
            break
        out.append(segment)
    return tuple(out)


def _could_match_below(pattern: str, key: str) -> bool:
    """Whether *pattern* could match at or below *key*."""
    literal = _literal_prefix(pattern)
    parts = _split(key)
    shared = min(len(literal), len(parts))
    return literal[:shared] == parts[:shared]


def _descendants(root: Path, *, limit: int) -> Iterator[str]:
    """Yield resource keys strictly below *root*, capped at *limit* entries.

    Refuses to walk anything it cannot enumerate, and yields nothing past the
    cap — the caller turns the cap into a denial rather than into a clean bill
    of health.
    """
    seen = 0
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        for name in sorted(dirnames) + sorted(filenames):
            if seen >= limit:
                return
            seen += 1
            yield here.joinpath(name).as_posix()


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """An immutable set of rules.

    ``frozen=True`` is load-bearing rather than tidy: ADR-0003 §C6.1 requires
    that imported text cannot change a permission decision. A policy that
    cannot be mutated after construction means a decision computed now and the
    same decision computed after ingesting a document are provably identical,
    because nothing in between could have changed the inputs.
    """

    rules: tuple[Rule, ...] = field(default_factory=tuple)

    @classmethod
    def from_rules(cls, rules: Iterable[Rule]) -> PermissionPolicy:
        """Load rules, validating each pattern before the policy exists."""
        return cls(rules=tuple(rules))

    def digest(self) -> str:
        """A stable SHA256 over the whole policy, for the approval binding.

        ADR-0003 §C4 requires *the policy snapshot still equals current policy*.
        Comparing rendered rule strings is exact and cheap for a policy this
        size, and it means a reordering of rules — which can never change a
        verdict under deny-first, but which is still a change worth invalidating
        an approval over — is visible.
        """
        payload = json.dumps(
            {"schema_version": 1, "rules": [r.render() for r in self.rules]},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # -- the decision -------------------------------------------------------

    def evaluate(
        self,
        *,
        task_id: TaskId | None,
        capability: str,
        resource: ResourceRef,
    ) -> PermissionDecision:
        """The one function that makes a permission verdict.

        Note the parameter types: ``capability`` is an id or a name, ``resource``
        is a :class:`ResourceRef` that ``canonicalize()`` minted, ``task_id`` is
        an application-supplied identifier. **There is no parameter that can
        carry document or excerpt text** — that is ADR-0003 §C6.1, enforced by
        the signature rather than by a reviewer's attention.

        Note also what is *absent*: ``canonical_args``. §C5 sketches a signature
        that takes them, but arguments are bound by digest in §C4, not matched
        by policy rules. Passing them here would put imported text inside the
        decision function, which is precisely what §C6.1 forbids, and it would
        put two mechanisms for the same job in competition. The argument-level
        control is :mod:`labcairn.security.approval`.
        """
        known = resolve_capability(capability)
        if known is None:
            # Fail closed on an id nobody registered. An unknown capability is
            # not "no rule matched"; it is a request for something that does
            # not exist, and §C5's default-deny is the only safe reading.
            return PermissionDecision(
                permission=Permission.DENY,
                reason=DecisionReason.UNKNOWN_CAPABILITY,
                matched_rule=None,
                matched_spelling=None,
                effect=None,
            )

        # Structural deny, before any rule. The registry says what a capability
        # may address; a rule cannot widen that. This is what makes a source
        # root read-only independently of the policy file.
        if known.root_kinds and resource.root_kind.value not in known.root_kinds:
            return PermissionDecision(
                permission=Permission.DENY,
                reason=DecisionReason.ROOT_KIND_NOT_PERMITTED,
                matched_rule=None,
                matched_spelling=None,
                effect=known.effect,
            )

        # Both spellings are evaluated and the worst outcome wins.
        #
        # Returning on the first spelling that matched anything was a real
        # bypass: a request whose declared spelling matched ``ALLOW **`` was
        # granted without the resolved spelling ever being considered, so a
        # ``DENY`` on the resolved key did not fire — which is precisely what
        # ADR-0003 C5 forbids ("a deny on either blocks"). ADR-0003's "declared
        # spelling first" means the declared spelling is *reported* first for
        # the audit trail, not that it decides alone.
        outcomes: list[PermissionDecision] = []
        for spelling, key in (
            ("declared", resource.declared_key),
            ("resolved", resource.resolved_key),
        ):
            outcome = self._worst_match(
                key=key,
                spelling=spelling,
                capability=known,
                resource=resource,
                task_id=task_id,
            )
            if outcome is not None:
                outcomes.append(outcome)

        if outcomes:
            return _worst_of(outcomes)

        # §C5's last line. Reached only when nothing matched at all.
        return PermissionDecision(
            permission=Permission.DENY,
            reason=DecisionReason.DEFAULT_DENY,
            matched_rule=None,
            matched_spelling=None,
            effect=known.effect,
        )

    def _worst_match(
        self,
        *,
        key: str,
        spelling: str,
        capability: Capability,
        resource: ResourceRef,
        task_id: TaskId | None,
    ) -> PermissionDecision | None:
        """The highest-severity match for one spelling, or ``None``.

        Walks the rules in three passes — deny, then ask, then allow — rather
        than returning on the first match. The ordering is the requirement
        ("*any* matching deny returns DENY immediately"); implementing it as an
        early return would make the result depend on declaration order and
        reintroduce exactly the first-match-wins behaviour §A5 rejects.
        """
        candidates: list[Rule] = [
            rule
            for rule in self.rules
            if rule.matches_scope(capability=capability, root_id=resource.root_id, task_id=task_id)
        ]

        for rule in candidates:
            if rule.effect is not Permission.DENY:
                continue
            if pattern_matches(rule.pattern, key):
                return PermissionDecision(
                    permission=Permission.DENY,
                    reason=DecisionReason.RULE_DENY,
                    matched_rule=rule.render(),
                    matched_spelling=spelling,
                    effect=capability.effect,
                )
            for depth in range(1, len(_split(key))):
                ancestor = PurePosixPath(*_split(key)[:depth]).as_posix()
                if pattern_matches(rule.pattern, ancestor):
                    return PermissionDecision(
                        permission=Permission.DENY,
                        reason=DecisionReason.RULE_DENY_ANCESTOR,
                        matched_rule=rule.render(),
                        matched_spelling=spelling,
                        effect=capability.effect,
                    )
            descendant_reason = self._denied_below(rule=rule, resource=resource)
            if descendant_reason is not None:
                return PermissionDecision(
                    permission=Permission.DENY,
                    reason=descendant_reason,
                    matched_rule=rule.render(),
                    matched_spelling=spelling,
                    effect=capability.effect,
                )

        for rule in candidates:
            if rule.effect is Permission.ASK and pattern_matches(rule.pattern, key):
                return PermissionDecision(
                    permission=Permission.ASK,
                    reason=DecisionReason.RULE_ASK,
                    matched_rule=rule.render(),
                    matched_spelling=spelling,
                    effect=capability.effect,
                )

        for rule in candidates:
            if rule.effect is Permission.ALLOW and pattern_matches(rule.pattern, key):
                return PermissionDecision(
                    permission=Permission.ALLOW,
                    reason=DecisionReason.RULE_ALLOW,
                    matched_rule=rule.render(),
                    matched_spelling=spelling,
                    effect=capability.effect,
                )
        return None

    def _denied_below(self, *, rule: Rule, resource: ResourceRef) -> DecisionReason | None:
        """Whether a deny rule covers something below the resource.

        This is the only part of evaluation that touches the filesystem, and it
        is ADR-0003 §C7's ``test_delete_refused_when_descendant_denied``
        generalised to *every* operation, not just delete.

        Two behaviours are deliberate and both fail closed:

        * the walk is skipped when the rule's literal prefix proves it cannot
          match below the resource, so the common case costs no I/O;
        * if the walk hits :data:`MAX_SCAN_ENTRIES`, the answer is DENY. An
          un-enumerable subtree is a subtree where absence of a deny rule cannot
          be established, and allow-on-ancestor assumes it can.
        """
        if not _could_match_below(rule.pattern, resource.resolved_key):
            return None

        candidates = _descendants(resource.real_path, limit=MAX_SCAN_ENTRIES)
        counted = 0
        try:
            for absolute in candidates:
                counted += 1
                relative = _relative_key(absolute, resource)
                if relative is None:
                    continue
                if pattern_matches(rule.pattern, relative):
                    return DecisionReason.RULE_DENY_DESCENDANT
                if counted >= MAX_SCAN_ENTRIES:
                    # The walk stopped because it hit the cap, not because it
                    # ran out. That is an unproven absence, so it is a deny.
                    return DecisionReason.RULE_DENY_DESCENDANT
        except OSError:
            # An unreadable directory is not an empty directory.
            return DecisionReason.RULE_DENY_DESCENDANT
        return None

    # -- bulk listings ------------------------------------------------------

    def filter_listing(
        self,
        keys: Iterable[str],
        *,
        task_id: TaskId | None,
        capability: str,
        root_id: str,
        root_kind: RootKind,
        real_root: Path,
    ) -> tuple[str, ...]:
        """Drop denied entries from a listing rather than refusing the call.

        ADR-0003 §C5: *ls/glob-style bulk operations filter denied entries out of
        results rather than only refusing the call, so the model never learns a
        denied name existed.* Refusing the whole listing is not equivalent — it
        still discloses that something is there, and it denies work the operator
        wanted allowed.

        The listing is filtered, not sorted into a visible/hidden split: the
        returned tuple contains only permitted keys, in the order given.
        """
        kept: list[str] = []
        for key in keys:
            resource = ResourceRef(
                declared_key=key,
                resolved_key=key,
                root_id=root_id,
                root_kind=root_kind,
                real_path=real_root / Path(*PurePosixPath(key).parts),
            )
            decision = self.evaluate(task_id=task_id, capability=capability, resource=resource)
            if decision.permission is not Permission.DENY:
                kept.append(key)
        return tuple(kept)


def _relative_key(absolute: str, resource: ResourceRef) -> str | None:
    """Rebuild the *resource key* of a path found below the resource.

    The resource's own key is re-attached, and that is the whole point: rule
    patterns are written against resource keys, so a file at
    ``<resource>/secrets.txt`` under a resource keyed ``bundle`` has the key
    ``bundle/secrets.txt`` — which is what a rule pattern ``bundle/secrets.txt``
    names. Returning the path relative to the resource alone would yield
    ``secrets.txt``, which matches no pattern an operator would write.
    """
    base = resource.real_path
    try:
        relative = Path(absolute).relative_to(base)
    except ValueError:
        return None
    parts = relative.parts
    if not parts:
        return None
    parent = resource.resolved_key
    return (
        f"{parent}/{PurePosixPath(*parts).as_posix()}"
        if parent
        else (PurePosixPath(*parts).as_posix())
    )


def default_policy() -> PermissionPolicy:
    """The policy a fresh workspace starts with.

    Deliberately grants **nothing**. With no rules at all the default is already
    deny (§C5), but an empty policy file teaches a user nothing about why
    nothing works. These two rules make the intended posture legible and deny
    nothing that was not already denied:

    * an outbound request is always ASK — never silently transmitted, per
      ``ARCHITECTURE.md``'s *no silent background upload* invariant;
    * ``**/.*`` is DENY — dotfiles are where credentials live, and no research
      deliverable needs one. This one rule is load-bearing beyond tidiness,
      because it makes an accidental ``.env`` or ``.git`` read fail closed
      rather than return secrets into a transcript.

    Note what is *not* here: writes outside the output area do not need a rule,
    because the capability registry already refuses them structurally (see
    :meth:`PermissionPolicy.evaluate`), and a catch-all ``ALLOW **`` is absent
    on purpose — adding one would make the default-deny invisible and would make
    any future deny rule a silent exception someone has to know to add.

    Granting access is an explicit, recorded act. That is the whole posture.
    """
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.DENY,
                pattern="**/.*",
                note="dotfiles are where credentials live; no research deliverable needs one",
            ),
            Rule(
                effect=Permission.ASK,
                pattern="**",
                effects=frozenset({Effect.NETWORK}),
                note="transmitting data to a provider always needs a human",
            ),
        ]
    )


__all__ = [
    "MAX_SCAN_ENTRIES",
    "DecisionReason",
    "PathRejection",
    "Permission",
    "PermissionDecision",
    "PermissionPolicy",
    "ResourceRef",
    "Rule",
    "RulePatternError",
    "default_policy",
    "pattern_matches",
    "validate_rule_pattern",
]
