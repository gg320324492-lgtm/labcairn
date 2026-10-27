"""Policy evaluation: deny-first, default-deny, and the refusals that must fire.

The three tests this file exists for are the direct contrast with the upstream
ADR-0003 §A5 rejected:

* :func:`test_deny_beats_allow_and_ask` — deepagents resolves on *first match in
  declaration order* and its own suite asserts
  ``test_earlier_allow_wins_over_later_catch_all_deny`` as intended.
* :func:`test_ask_beats_allow` — the ordering §C5 requires, which is not what a
  first-match engine does.
* :func:`test_default_is_deny` — deepagents returns ``"allow"`` when no rule
  matches, and asserts ``test_default_effect_is_allow``.

The rest cover what §C5 adds: both path spellings matched, ancestor and
descendant denies applying to *every* operation, bulk listings filtered rather
than refused, and rule patterns validated at load.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from labcairn.core.ids import TaskId, new_id
from labcairn.security.capabilities import (
    CAPABILITIES,
    CapabilityId,
    Effect,
    looks_like_execution,
)
from labcairn.security.paths import RootKind, bind_root
from labcairn.security.policy import (
    DecisionReason,
    Permission,
    PermissionPolicy,
    ResourceRef,
    Rule,
    RulePatternError,
    default_policy,
    pattern_matches,
    validate_rule_pattern,
)
from labcairn.workspace import Workspace

pytestmark = pytest.mark.unit


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "out"
    directory.mkdir()
    return directory


def make_ref(
    *,
    key: str = "report.md",
    declared: str | None = None,
    root_kind: RootKind = RootKind.OUTPUT,
    real_path: Path | None = None,
    root_id: str = "out",
) -> ResourceRef:
    return ResourceRef(
        declared_key=declared if declared is not None else key,
        resolved_key=key,
        root_id=root_id,
        root_kind=root_kind,
        real_path=real_path if real_path is not None else Path("unused") / key,
    )


# ---------------------------------------------------------------------------
# The three ordering rules
# ---------------------------------------------------------------------------


def test_deny_beats_allow_and_ask(root: Path) -> None:
    """§C5: *any matching deny returns DENY immediately*.

    The allow is listed **first** on purpose. An engine that returns on first
    match — which is what deepagents does, and what its own test suite asserts
    as correct — would answer ALLOW here and pass the upstream's own test while
    failing this one.
    """
    policy = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.ALLOW, pattern="**"),
            Rule(effect=Permission.ASK, pattern="**"),
            Rule(effect=Permission.DENY, pattern="secrets.txt"),
        ]
    )
    decision = policy.evaluate(
        task_id=None, capability="fs.write", resource=make_ref(key="secrets.txt")
    )
    assert decision.permission is Permission.DENY
    assert decision.reason is DecisionReason.RULE_DENY


def test_ask_beats_allow(root: Path) -> None:
    """§C5's second step: any matching ask returns ASK."""
    policy = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.ALLOW, pattern="**"),
            Rule(effect=Permission.ASK, pattern="private/**"),
        ]
    )
    decision = policy.evaluate(
        task_id=None, capability="fs.write", resource=make_ref(key="private/a.md")
    )
    assert decision.permission is Permission.ASK


def test_default_is_deny(root: Path) -> None:
    """§C5: *no matching rule returns DENY*.

    Asserted with an empty policy, so it cannot pass because some rule happened
    to fire.
    """
    policy = PermissionPolicy()
    decision = policy.evaluate(task_id=None, capability="fs.write", resource=make_ref())
    assert decision.permission is Permission.DENY
    assert decision.reason is DecisionReason.DEFAULT_DENY


def test_an_unrelated_rule_does_not_grant_a_broad_allow(root: Path) -> None:
    """An allow for one path must not become the default for everything else."""
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="only-this.md")])
    decision = policy.evaluate(
        task_id=None, capability="fs.write", resource=make_ref(key="other.md")
    )
    assert decision.permission is Permission.DENY


def test_rule_declaration_order_does_not_change_the_verdict(root: Path) -> None:
    """The same three rules, in six orders, always reach the same answer.

    This is the strongest form of the deny-first property: it is not that deny
    happens to be checked first, but that *no* ordering can produce allow.
    """
    rules = [
        Rule(effect=Permission.ALLOW, pattern="**"),
        Rule(effect=Permission.ASK, pattern="sub/**"),
        Rule(effect=Permission.DENY, pattern="sub/secret.md"),
    ]
    expected: set[Permission] = set()
    from itertools import permutations

    for ordering in permutations(rules):
        policy = PermissionPolicy.from_rules(ordering)
        decision = policy.evaluate(
            task_id=None,
            capability="fs.write",
            resource=make_ref(key="sub/secret.md"),
        )
        expected.add(decision.permission)
    assert expected == {Permission.DENY}


# ---------------------------------------------------------------------------
# Unknown capabilities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unknown",
    ["fs.writex", "fs.Write", "FS.WRITE", "", "shell", "exec", "eval", "python", "os.system"],
)
def test_unknown_capability_is_denied(root: Path, unknown: str) -> None:
    """Fail closed on an id nobody registered.

    Not an exception: an exception is a crash a caller might catch and carry on
    from. This is a verdict.
    """
    permissive = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    decision = permissive.evaluate(task_id=None, capability=unknown, resource=make_ref())
    assert decision.permission is Permission.DENY
    assert decision.reason is DecisionReason.UNKNOWN_CAPABILITY


def test_an_allow_rule_cannot_resurrect_an_unknown_capability(root: Path) -> None:
    """The catch-all allow must not turn "not a capability" into a permission.

    This is the specific combination that fails closed: if the registry lookup
    happened *after* the rule scan, ``ALLOW **`` would grant a capability that
    does not exist.
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    decision = policy.evaluate(task_id=None, capability="totally.made.up", resource=make_ref())
    assert decision.permission is Permission.DENY


def test_the_registry_contains_no_execution_capability() -> None:
    """Phase 1 has no arbitrary shell or Python, and the omission is asserted.

    ``docs/ARCHITECTURE.md`` forbids it; ADR-0003 §Re-evaluation trigger 2 says
    the permission model cannot express an open execution surface. So this is a
    property the design rests on, not an oversight to fill in later.
    """
    offenders = {
        cap: token for cap in CAPABILITIES if (token := looks_like_execution(cap)) is not None
    }
    assert offenders == {}, f"a registered capability would permit code execution: {offenders}"


@pytest.mark.parametrize(
    ("id_", "expected_token"),
    [
        ("shell.exec", "shell"),
        ("fs.exec_file", "exec"),
        ("os.system", "system"),
        ("run_python", "python"),
        ("python3", "python"),
        ("plugin.load", "plugin"),
        # The false positive a substring check would produce: "retrieval"
        # contains "eval". Token matching must not flag it.
        ("retrieval.query", None),
        ("fs.read", None),
        ("analysis.run", None),
    ],
)
def test_the_execution_check_is_token_based_not_substring(
    id_: str, expected_token: str | None
) -> None:
    """Why the check splits on separators instead of using ``in``.

    A substring check rejects ``retrieval.query`` (because "retr**ieval**"
    contains "eval") while still accepting ``fs.exec_helper``'s cousin
    ``fs.helper`` — it is both too strict and too lax, which is the worst
    combination for a security invariant.
    """
    assert looks_like_execution(id_) == expected_token


def test_model_request_is_the_only_network_capability() -> None:
    """ADR-0003 §C6.4: local and outbound are *separate* capabilities.

    If a second network capability appeared, "deny all outbound" would stop
    being one rule and become an audit of every tool — which is how a local
    analysis silently starts uploading.
    """
    network = sorted(c for c, v in CAPABILITIES.items() if v.effect is Effect.NETWORK)
    assert network == ["model.request"]


# ---------------------------------------------------------------------------
# Structural: root kind
# ---------------------------------------------------------------------------


def test_a_write_capability_cannot_target_a_source_root() -> None:
    """Read-only source material is enforced by the registry, not by a rule.

    An explicit ``allow`` for the write capability against the source root is
    present and is still denied: the registry's ``root_kinds`` is a floor that
    policy adds to, not something policy can override.
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="a.pdf", root_kind=RootKind.SOURCE),
    )
    assert decision.permission is Permission.DENY
    assert decision.reason is DecisionReason.ROOT_KIND_NOT_PERMITTED


def test_the_structural_check_precedes_even_a_deny_rule(root: Path) -> None:
    """Both are denials; the structural one is reported because it is first.

    Recording the *structural* reason is what lets an operator tell "I wrote a
    rule that was wrong" from "this capability was never able to do that".
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])
    decision = policy.evaluate(
        task_id=None,
        capability="artifact.write",
        resource=make_ref(key="a.pdf", root_kind=RootKind.SOURCE),
    )
    assert decision.reason is DecisionReason.ROOT_KIND_NOT_PERMITTED


def test_reading_a_source_root_is_permitted_when_a_rule_says_so() -> None:
    """The structural floor is not "deny everything"; reads are legitimate."""
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    decision = policy.evaluate(
        task_id=None,
        capability="source.read",
        resource=make_ref(key="paper.pdf", root_kind=RootKind.SOURCE),
    )
    assert decision.permission is Permission.ALLOW


# ---------------------------------------------------------------------------
# Both spellings
# ---------------------------------------------------------------------------


def test_a_deny_on_the_resolved_spelling_blocks(root: Path) -> None:
    """The rule names the real file; the caller named the symlink."""
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="secret.md")])
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="secret.md", declared="alias.md"),
    )
    assert decision.permission is Permission.DENY
    assert decision.matched_spelling == "resolved"


def test_a_deny_on_the_declared_spelling_blocks(root: Path) -> None:
    """The rule names the symlink's own name, not what it points at."""
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="alias.md")])
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="ok.md", declared="alias.md"),
    )
    assert decision.permission is Permission.DENY
    assert decision.matched_spelling == "declared"


def test_declared_is_checked_before_resolved(root: Path) -> None:
    """When both spellings match different rules, the declared one is reported.

    Both are denied either way; recording which fired is what makes a symlink
    denial legible in an audit trail rather than a bare DENY.
    """
    policy = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.DENY, pattern="alias.md"),
            Rule(effect=Permission.DENY, pattern="secret.md"),
        ]
    )
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="secret.md", declared="alias.md"),
    )
    assert decision.matched_spelling == "declared"


# ---------------------------------------------------------------------------
# Ancestors and descendants
# ---------------------------------------------------------------------------


def test_a_deny_on_an_ancestor_blocks(root: Path) -> None:
    """Denying a directory denies everything below it.

    The pattern is ``private`` — a *literal* directory name that does not match
    the full key. If the pattern were ``private/**`` it would match the key
    directly and this would be testing the ordinary path, not the ancestor walk.
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="private")])
    first = policy.evaluate(
        task_id=None, capability="fs.write", resource=make_ref(key="private/deep/report.md")
    )
    assert first.permission is Permission.DENY
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="private/deep/report.md"),
    )
    assert decision.reason is DecisionReason.RULE_DENY_ANCESTOR


def test_a_descendant_pattern_deny_matches_the_full_key_directly(root: Path) -> None:
    """The other half: ``private/**`` matches the key itself, not via an ancestor.

    Recorded so the two DENY reasons are distinguishable — a reader debugging a
    denial needs to know which walk produced it.
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="private/**")])
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="private/deep/report.md"),
    )
    assert decision.reason is DecisionReason.RULE_DENY


def test_a_deny_on_a_descendant_blocks_the_parent(root: Path, tmp_path: Path) -> None:
    """§C7's ``test_delete_refused_when_descendant_denied``, generalised.

    deepagents applies this only to recursive delete. §C7 says the behaviour
    "now holds for all operations, not just delete" — so an allow for a
    directory cannot be trusted when a more specific deny may cover one entry
    below it, and nothing is allowed on speculation.
    """
    directory = tmp_path / "bundle"
    directory.mkdir()
    (directory / "secrets.txt").write_text("s", encoding="utf-8")
    policy = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.ALLOW, pattern="bundle/**"),
            Rule(effect=Permission.DENY, pattern="bundle/secrets.txt"),
        ]
    )
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="bundle", real_path=directory),
    )
    assert decision.permission is Permission.DENY
    assert decision.reason is DecisionReason.RULE_DENY_DESCENDANT


def test_a_descendant_deny_does_not_fire_when_the_rule_cannot_reach_below(root: Path) -> None:
    """The cheap pre-filter, so the walk does not run for unrelated rules.

    Also asserts the rule genuinely does not match: without this the walk could
    deny everything and the test would still pass.
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="elsewhere/**")])
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="report.md"),
    )
    assert decision.permission is Permission.DENY
    assert decision.reason is DecisionReason.DEFAULT_DENY, "not a descendant denial"


def test_an_allow_is_not_overturned_by_a_descendant_of_an_unrelated_path(root: Path) -> None:
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="reports/**")])
    decision = policy.evaluate(
        task_id=None,
        capability="fs.write",
        resource=make_ref(key="reports/q1.md"),
    )
    assert decision.permission is Permission.ALLOW


# ---------------------------------------------------------------------------
# Bulk listings
# ---------------------------------------------------------------------------


def test_denied_entries_are_filtered_out_of_a_listing(root: Path) -> None:
    """§C5: filter, do not refuse.

    A refused listing still tells the model that something is there. The
    returned tuple must simply not contain the denied name.
    """
    policy = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.ALLOW, pattern="**"),
            Rule(effect=Permission.DENY, pattern="private/**"),
        ]
    )
    kept = policy.filter_listing(
        ["a.md", "private/b.md", "c.md", "private/deep/d.md"],
        task_id=None,
        capability="fs.list",
        root_id="out",
        root_kind=RootKind.OUTPUT,
        real_root=root,
    )
    assert kept == ("a.md", "c.md")
    assert all("private" not in entry for entry in kept)


def test_a_listing_refused_by_default_is_empty_not_an_error(root: Path) -> None:
    """Under default-deny, a listing is empty rather than an exception."""
    kept = PermissionPolicy().filter_listing(
        ["a.md", "b.md"],
        task_id=None,
        capability="fs.list",
        root_id="out",
        root_kind=RootKind.OUTPUT,
        real_root=root,
    )
    assert kept == ()


# ---------------------------------------------------------------------------
# Pattern validation at load
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "why"),
    [
        ("/etc/passwd", "absolute"),
        ("C:/Windows", "drive letter"),
        ("../outside", "'..' segment"),
        ("a/../../b", "'..' segment in the middle"),
        ("~/secrets", "home expansion"),
        ("~root/secrets", "home expansion"),
        ("", "empty"),
        ("   ", "whitespace"),
        ("a\\b", "backslash separator"),
    ],
)
def test_rule_patterns_are_rejected_at_load(pattern: str, why: str) -> None:
    """ADR-0003 §C5: *rule patterns are validated at load*.

    Validating at load rather than at match time means a policy that exists has
    already had every pattern proved unambiguous, so the decision path never has
    to decide whether a pattern is safe to interpret.
    """
    with pytest.raises(RulePatternError):
        validate_rule_pattern(pattern)
    with pytest.raises(RulePatternError):
        Rule(effect=Permission.DENY, pattern=pattern)


def test_an_empty_scope_is_rejected_rather_than_meaning_nothing() -> None:
    """``None`` means "any"; an empty set would mean "none" and is never intended."""
    with pytest.raises(RulePatternError):
        Rule(effect=Permission.DENY, pattern="**", root_ids=frozenset())


@pytest.mark.parametrize(
    ("pattern", "key", "expected"),
    [
        ("*.md", "a.md", True),
        ("*.md", "a.txt", False),
        ("**", "a/b/c.md", True),
        ("a/*", "a/b.md", True),
        ("a/*", "a/b/c.md", False),  # single star must not cross a separator
        ("a/**", "a/b/c.md", True),
        ("a/**", "a", True),
        ("**/secret*", "deep/nested/secret1.md", True),
        ("**/.*", "a/.env", True),
        ("**/.*", "a/visible.md", False),
    ],
)
def test_pattern_matching_semantics(pattern: str, key: str, expected: bool) -> None:
    """``*`` stays inside a segment; ``**`` spans them.

    The distinction is what makes a deny rule mean what it looks like. With
    ``*`` crossing separators, a rule reading ``a/*`` would silently cover the
    whole subtree, and an operator could not reason about its blast radius.
    """
    assert pattern_matches(pattern, key) is expected


# ---------------------------------------------------------------------------
# Task scope
# ---------------------------------------------------------------------------


def test_a_rule_scoped_to_one_task_does_not_apply_to_another() -> None:
    only_this = TaskId(new_id())
    other = TaskId(new_id())
    policy = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ALLOW, pattern="**", task_ids=frozenset({str(only_this)}))]
    )
    allowed = policy.evaluate(task_id=only_this, capability="fs.write", resource=make_ref())
    assert allowed.permission is Permission.ALLOW
    decision = policy.evaluate(task_id=other, capability="fs.write", resource=make_ref())
    assert decision.permission is Permission.DENY


# ---------------------------------------------------------------------------
# Policy digest and immutability
# ---------------------------------------------------------------------------


def test_the_policy_digest_is_stable_and_order_sensitive() -> None:
    """§C4: *the policy snapshot still equals current policy*.

    Reordering rules can never change a verdict under deny-first, but it is still
    a change to the snapshot, and an approval bound to the old one should stop
    being honoured rather than quietly continuing.
    """
    a = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ALLOW, pattern="x"), Rule(effect=Permission.DENY, pattern="y")]
    )
    same = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ALLOW, pattern="x"), Rule(effect=Permission.DENY, pattern="y")]
    )
    reordered = PermissionPolicy.from_rules(
        [Rule(effect=Permission.DENY, pattern="y"), Rule(effect=Permission.ALLOW, pattern="x")]
    )
    assert a.digest() == same.digest()
    assert a.digest() != reordered.digest()


def test_the_policy_is_frozen() -> None:
    """Imported text must not be able to change a policy.

    ADR-0003 §C6.1: the decision is unreachable from imported content *by
    construction*. Frozen rules are what make "the decision is identical before
    and after ingesting a document" a proof rather than an observation.
    """
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    with pytest.raises(Exception):  # noqa: B017 - frozen dataclass raises FrozenInstanceError
        policy.rules = ()  # type: ignore[misc]


def test_the_default_policy_grants_nothing() -> None:
    """A fresh workspace denies everything except asking about outbound.

    The assertion is that *no* capability on an ordinary path is allowed. If a
    catch-all ``ALLOW **`` is ever added to :func:`default_policy`, this fails —
    which is the point: granting should be a visible, explicit act.
    """
    policy = default_policy()
    for capability in CAPABILITIES:
        decision = policy.evaluate(
            task_id=None,
            capability=capability,
            resource=make_ref(key="report.md", root_kind=RootKind.OUTPUT),
        )
        if CAPABILITIES[capability].effect is Effect.NETWORK:
            assert decision.permission is Permission.ASK, capability
        else:
            assert decision.permission is Permission.DENY, (
                f"{capability} is allowed by the default policy; default_policy must grant nothing"
            )


def test_the_default_policy_asks_before_any_transmission() -> None:
    """ "No silent background upload" is a rule, not an intention."""
    policy = default_policy()
    decision = policy.evaluate(
        task_id=None,
        capability="model.request",
        resource=make_ref(key="excerpt.md", root_kind=RootKind.SOURCE),
    )
    assert decision.permission is Permission.ASK
    assert decision.effect is Effect.NETWORK


def test_the_default_policy_denies_dotfiles() -> None:
    """.env and .git are where credentials live; no deliverable needs one."""
    policy = default_policy()
    for key in (".env", "a/.env", "config/.secrets"):
        decision = policy.evaluate(
            task_id=None,
            capability="source.read",
            resource=make_ref(key=key, root_kind=RootKind.SOURCE),
        )
        assert decision.permission is Permission.DENY, key


# ---------------------------------------------------------------------------
# Every capability is reachable and closed
# ---------------------------------------------------------------------------


def test_every_capability_declares_a_closed_argument_model() -> None:
    """§C6.2: unknown keys are rejected.

    Asserted over the whole registry rather than a sample, because a capability
    added later with an open model is exactly the regression.
    """
    for capability in CAPABILITIES.values():
        assert capability.args_model.model_config.get("extra") == "forbid", (
            f"{capability.capability_id.value} has an open argument model"
        )


def test_every_capability_has_a_distinct_id_matching_its_enum_member() -> None:
    for key, capability in CAPABILITIES.items():
        assert key == capability.capability_id.value
        assert CapabilityId(key) is capability.capability_id


def test_roots_are_bound_with_a_resolvable_directory(tmp_path: Path) -> None:
    """Smoke: the fixture path used by the workspace tests is bindable."""
    bound = bind_root("out", tmp_path, RootKind.OUTPUT)
    assert bound.path == tmp_path.resolve()


def test_a_deny_on_the_resolved_spelling_beats_an_allow_on_the_declared_one(
    tmp_path: Path,
) -> None:
    """ADR-0003 C5: "a deny on **either** blocks".

    Cross-review found this reachable. ``evaluate`` returned on the first
    spelling that matched anything, so a request whose *declared* spelling hit
    ``ALLOW **`` was granted and the *resolved* spelling — the one carrying the
    deny — was never evaluated. On a case-insensitive filesystem that turned a
    deny rule into one that changing the case of a filename bypasses.
    """
    root = tmp_path / "ws"
    (root / "private").mkdir(parents=True)
    (root / "private" / "secrets.txt").write_text("salary data", encoding="utf-8")

    workspace = Workspace.bind(root, task_id=TaskId(new_id()))
    policy = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.DENY, pattern="private/secrets.txt"),
            Rule(effect=Permission.ALLOW, pattern="**"),
        ]
    )

    # Both spellings resolve to one real file on Windows. ResourceRef carries
    # them separately, which is exactly the shape evaluate() has to reconcile.
    direct = make_ref(
        key="private/secrets.txt",
        declared="private/secrets.txt",
        root_kind=RootKind.SOURCE,
        real_path=root / "private" / "secrets.txt",
    )
    assert (
        policy.evaluate(
            task_id=workspace.task_id, capability=CapabilityId.FS_READ, resource=direct
        ).permission
        is Permission.DENY
    )

    if os.name != "nt":
        # The bypass needed a case-insensitive filesystem; elsewhere the two
        # spellings are genuinely different files and there is nothing to prove.
        return

    # On Windows these are the same file. Before the fix this returned ALLOW.
    same_file_other_case = make_ref(
        key="private/secrets.txt",  # the resolved spelling, lower case
        declared="private/SECRETS.TXT",  # what the caller actually asked for
        root_kind=RootKind.SOURCE,
        real_path=root / "private" / "secrets.txt",
    )
    decision = policy.evaluate(
        task_id=workspace.task_id,
        capability=CapabilityId.FS_READ,
        resource=same_file_other_case,
    )
    assert decision.permission is Permission.DENY, f"case alone bypassed a deny rule: {decision}"
