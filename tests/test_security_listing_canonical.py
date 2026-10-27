"""The policy must be matched on the canonical entry, not the declared spelling.

ADR-0011. The bug these tests exist for was demonstrated rather than
theorised: with ``DENY source.inventory private/**`` and a symlink
``public/hop -> private``, ``read("public/hop/secret.md")`` returned the
denied file's bytes, and the listing showed the symlink as an ordinary
entry. The deny rule did not stop it, and neither did ``DENY
private/secret.md`` nor ``DENY **/secret.md``.

These are in the security layer's own tests rather than the ingestion
layer's, because the layer that was wrong is the one that must not be
wrong again. The one contract that is about ingestion rather than about
the boundary -- that the walk does not store denied bytes -- lives with
the walk in ``tests/test_material_walk.py``.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from labcairn.core.ids import TaskId, new_id
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.workspace.readonly import (
    SourceAccessDeniedError,
    SourceIsReadOnlyError,
    SourceMaterial,
)
from labcairn.workspace.roots import Workspace

pytestmark = pytest.mark.negative

NL = chr(10)
CAPABILITY = CapabilityId.SOURCE_INVENTORY.value
_DENY_PRIVATE = Rule(
    effect=Permission.DENY,
    pattern="private/**",
    capabilities=frozenset({CAPABILITY}),
)


@pytest.fixture
def workspace_with_symlink(tmp_path: pathlib.Path) -> tuple[Workspace, str]:
    """A permitted directory holding a symlink into a denied one."""
    root = tmp_path / "ws"
    sources = root / "sources"
    (sources / "public").mkdir(parents=True)
    (sources / "private").mkdir(parents=True)
    (sources / "private" / "secret.md").write_text("# SECRET" + NL, encoding="utf-8")
    (sources / "public" / "ok.md").write_text("# fine" + NL, encoding="utf-8")
    link = sources / "public" / "hop"
    try:
        link.symlink_to(sources / "private", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable on this platform or filesystem")
    workspace = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    return workspace, workspace.source_roots[0].root_id


@pytest.fixture
def workspace_with_junction(tmp_path: pathlib.Path) -> tuple[Workspace, str]:
    """The same shape, but the hop is a real NTFS **junction**.

    A junction is not a symbolic link: ``is_symlink()`` is false for one, and
    they are different reparse points with different reasons to be created.
    The repository treats them separately, and the ADR records that a junction
    leaked the same way a symlink did -- so "the fix covers the thing the ADR
    names" has to be measured for both, not argued from the symlink case.
    """
    if os.name != "nt":
        pytest.skip("directory junctions are a Windows facility")
    root = tmp_path / "ws"
    sources = root / "sources"
    (sources / "public").mkdir(parents=True)
    (sources / "private").mkdir(parents=True)
    (sources / "private" / "secret.md").write_text("# SECRET" + NL, encoding="utf-8")
    (sources / "public" / "ok.md").write_text("# fine" + NL, encoding="utf-8")
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(sources / "public" / "hop"), str(sources / "private")],
        capture_output=True,
        check=False,
    )
    if made.returncode != 0:
        pytest.skip("junction creation refused on this filesystem")
    hop = sources / "public" / "hop"
    assert not hop.is_symlink(), "mklink made a symlink; this test is not testing a junction"
    workspace = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    return workspace, workspace.source_roots[0].root_id


def _policy(*extra: Rule) -> PermissionPolicy:
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CAPABILITY}),
            ),
            *extra,
        ]
    )


def test_a_symlink_into_a_denied_directory_is_not_listed(
    workspace_with_symlink: tuple[Workspace, str],
) -> None:
    """Contract 1.

    The listing evaluates the policy on the canonical entry, so the symlink
    is judged by where it points, not by what it is called.
    """
    workspace, root_id = workspace_with_symlink
    material = SourceMaterial(
        workspace,
        _policy(_DENY_PRIVATE),
    )
    listing = material.list_dir("public", root_id=root_id)
    assert "public/hop" not in listing, listing
    assert "public/ok.md" in listing, "a permitted file was hidden"


def test_reading_through_the_denied_path_is_refused(
    workspace_with_symlink: tuple[Workspace, str],
) -> None:
    """Contract 2. Refused, not filtered -- a single read has no results to
    drop it from."""
    workspace, root_id = workspace_with_symlink
    material = SourceMaterial(
        workspace,
        _policy(_DENY_PRIVATE),
    )
    with pytest.raises(SourceAccessDeniedError):
        material.read_permitted("public/hop/secret.md", root_id=root_id, capability=CAPABILITY)


def test_read_permitted_still_reads_what_is_permitted(
    workspace_with_symlink: tuple[Workspace, str],
) -> None:
    """Contract 5. The protected read is not a filter that eats everything."""
    workspace, root_id = workspace_with_symlink
    material = SourceMaterial(workspace, _policy())
    data = material.read_permitted("public/ok.md", root_id=root_id, capability=CAPABILITY)
    assert b"fine" in data


def test_read_remains_the_unchecked_primitive(
    workspace_with_symlink: tuple[Workspace, str],
) -> None:
    """Contract 4, and the honesty the docstring promises.

    ``read`` checks *whose* material it is, not whether this caller may
    have it. It is unchanged, and a caller using it to read denied
    material is using it correctly and skipping a check that was its own
    job to do.
    """
    workspace, root_id = workspace_with_symlink
    material = SourceMaterial(
        workspace,
        _policy(_DENY_PRIVATE),
    )
    data = material.read("public/hop/secret.md", root_id=root_id)
    assert b"SECRET" in data, "read changed behaviour; it is meant to stay the unchecked primitive"


def test_a_denial_is_not_confused_with_a_write_refusal() -> None:
    """A caller that turns path errors into tool errors must not swallow a
    policy outcome, so the two are different exception types."""
    assert not issubclass(SourceAccessDeniedError, SourceIsReadOnlyError)
    assert not issubclass(SourceIsReadOnlyError, SourceAccessDeniedError)


def test_a_caller_without_a_resolver_keeps_the_previous_behaviour(
    tmp_path: pathlib.Path,
) -> None:
    """Contract 6. ``filter_listing`` is public and has callers that have no
    workspace to resolve against; their behaviour must not change."""
    from labcairn.security.policy import PermissionPolicy as Policy

    policy = Policy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CAPABILITY}),
            ),
            _DENY_PRIVATE,
        ]
    )
    from labcairn.security.paths import RootKind

    kept = policy.filter_listing(
        ["public/ok.md", "private/secret.md"],
        task_id=None,
        capability=CAPABILITY,
        root_id="source:0",
        root_kind=RootKind.SOURCE,
        real_root=tmp_path,
    )
    assert list(kept) == ["public/ok.md"], kept


# Contract 3 -- the walk does not ingest a denied symlink -- is an end-to-end
# assertion about ingestion and the store, so it lives with the walk in
# tests/test_material_walk.py, where the database fixture already is. Asserting
# it here as well would buy a second copy of the same behaviour, not coverage.


def test_a_junction_into_a_denied_directory_is_not_listed(
    workspace_with_junction: tuple[Workspace, str],
) -> None:
    """Contracts 1 and 5, for a junction rather than a symlink.

    The ADR records that a junction leaked the same way a symlink did, so the
    fix has to be measured on the thing the ADR names. Asserting it from the
    symlink case would be an argument, not a measurement: a junction is a
    different reparse point, and whatever resolves one is not thereby proven to
    resolve the other.
    """
    workspace, root_id = workspace_with_junction
    material = SourceMaterial(workspace, _policy(_DENY_PRIVATE))
    listing = material.list_dir("public", root_id=root_id)
    assert "public/hop" not in listing, "the junction was listed"
    assert "public/ok.md" in listing, "a permitted file was hidden"


def test_reading_through_a_denied_junction_is_refused(
    workspace_with_junction: tuple[Workspace, str],
) -> None:
    """Contract 2, for a junction. Both layers, since a junction is exactly
    the case where a listing that looks right is not enough."""
    workspace, root_id = workspace_with_junction
    material = SourceMaterial(workspace, _policy(_DENY_PRIVATE))
    with pytest.raises(SourceAccessDeniedError):
        material.read_permitted("public/hop/secret.md", root_id=root_id, capability=CAPABILITY)
