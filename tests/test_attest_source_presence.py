"""The attestation asks the source again, at the door to a citable status.

ADR-0004 I4: a record whose ``source_content_hash`` no longer matches the
source is *invalidated*, not refreshed, and a source row the ledger no longer
holds is the strongest case of that -- the hash cannot be observed at all. The
acceptance record
``docs/acceptance/LC-P4-PILOT-dangling-source-ids-2026-11-26.md`` measured a
record reaching ``user_attested``, a state a report may cite, while its anchor
named a source the ledger had dropped. This file holds the fix still.

**The rule, and where it lives.** A record may not reach a citable status while
any anchor it rests on names a source the ledger no longer holds, or while that
source's current content hash no longer matches the hash the anchor was bound
to. The check is C1 -- ``labcairn.evidence.checks.c1.check_source_exists``, the
callable ADR-0004 fixes the home and signature of -- run by the store at the
attestation, the same check ``advance`` runs before ``verified_by_rule``. So the
CLI, the API and any future face inherit one answer rather than each spelling
its own, and there is no second implementation of the rule to drift out of step.

**What is witnessed here.**

* a present, unchanged source still attests -- the control that the check is not
  vacuously refusing everything;
* a source the ledger no longer holds refuses the store's ``attest`` with a
  :class:`~labcairn.evidence.store.DanglingSourceError` that names the source,
  and leaves the record ``extracted``;
* a source whose bytes moved under it (the hash no longer matches) refuses the
  same way -- ADR-0004 A2's drift, the case a hash cannot be refreshed past;
* the application's ``attest_claim`` maps that refusal onto its own code,
  ``CITATION_SOURCE_UNOBSERVABLE``, so a surface can branch on the reason.

Nothing under the local material area is read: the shape is built in a
workspace of its own, under a temporary directory, through the product's own
operations, and every row below is written by the product into its own
temporary database.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy import text as sql_text
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    ClaimRequest,
    attest_claim,
    create_task,
    ingest_material,
    list_source_addresses,
    record_claim,
)
from labcairn.application.material_ingestion import remove_source
from labcairn.cli.commands import EXIT_REFUSED
from labcairn.db.repository import load_source
from labcairn.evidence.index import load_anchor, read_content_hash
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import VerificationStatus
from labcairn.evidence.store import DanglingSourceError, attest, load_record
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

_MOMENT = dt.datetime(2026, 11, 27, tzinfo=dt.UTC)
_OTHER_SHA = "b" * 64

# The columns a source_texts row carries besides its id and its source hash.
# A drift is the bytes moving under one source id, so the texts are copied to
# the new hash and the source row is pointed at it -- the anchor's bound hash
# then no longer matches what the source currently holds.
_TEXT_COLUMNS = (
    "extraction_version, locator_kind, locator_key, page, line_start, line_end, "
    "section, row_number, column_name, sheet_name, cell_ref, docx_part, "
    "docx_element_path, docx_view, docx_char_start, docx_char_end, text, "
    "text_sha256, created_at"
)

_CSV_BODY = b"name,role\n4.2,control\n"


env = _shared_env


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A temp workspace, with MPLCONFIGDIR pinned inside it (the house rule)."""
    import os

    os.environ.setdefault("MPLCONFIGDIR", str(tmp_path / "mplconfig"))
    return tmp_path


def _allow_all() -> PermissionPolicy:
    """A policy that permits every capability, so the setup stays out of the way."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _a_context_all(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A task that holds the material, under a policy that allows the removal."""
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Watching the attestation ask the source",
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )


def _a_claim(
    env: StoreEnv, workspace_root: Path
) -> tuple[ApplicationContext, str, EvidenceRecord, str]:
    """A recorded claim over a present source: the shape before anything is taken.

    A material is ingested and a claim recorded at one of its addresses, so the
    ledger holds a source, an anchor into it bound to the source's current hash,
    and the ``extracted`` record that cites the anchor. The source is present and
    unchanged, so this is the shape an attestation must still accept.
    """
    materials = workspace_root / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    (materials / "one.csv").write_bytes(_CSV_BODY)
    context = _a_context_all(env, workspace_root)

    first = ingest_material(context, now=_MOMENT)
    source_id = first.source_ids[0]
    addresses = list_source_addresses(context, source_id)
    address = next(a for a in addresses if a.text == "4.2")
    recorded = record_claim(
        context,
        ClaimRequest(source_id=source_id, locator_key=address.locator_key, text="4.2"),
        now=_MOMENT,
    )
    record = recorded.record
    assert record.status is VerificationStatus.EXTRACTED
    return context, source_id, record, record.anchor_ids[0]


def _take_the_source_back(context: ApplicationContext, source_id: str) -> None:
    """Remove the source's row, the way the product does, leaving the anchor."""
    remove_source(context, source_id)


def _move_the_bytes_under_the_source(
    env: StoreEnv, source_id: str, new_sha: str = _OTHER_SHA
) -> None:
    """Make the source's current bytes differ from what the anchor was bound to.

    The texts are copied to *new_sha* and the source row is pointed at it, so
    the address still resolves but the source's current hash no longer matches
    the anchor's bound hash -- ADR-0004 A2's drift, reachable only by a change
    outside the product's own write path, which is why the attestation asks
    again rather than trusting the row.
    """
    session = env.session
    old_sha = read_content_hash(session.connection(), source_id)
    assert old_sha is not None and old_sha != new_sha
    session.execute(
        sql_text(
            f"INSERT INTO source_texts (source_content_sha256, {_TEXT_COLUMNS}) "
            f"SELECT :new, {_TEXT_COLUMNS} FROM source_texts "
            "WHERE source_content_sha256 = :old"
        ),
        {"new": new_sha, "old": old_sha},
    )
    session.execute(
        sql_text("UPDATE sources SET content_sha256 = :s WHERE source_id = :id"),
        {"s": new_sha, "id": source_id},
    )
    session.commit()


# --------------------------------------------------------------------------- #
# the control: a present source still attests
# --------------------------------------------------------------------------- #


def test_a_present_unchanged_source_still_attests(env: StoreEnv, workspace_root: Path) -> None:
    """The check is not a blanket refusal: a sound source is still citable.

    Without this, every refusal below could be the check refusing everything,
    and the property would be unheld. The source is present and unchanged, C1
    passes, and the attestation reaches ``user_attested``.
    """
    _context, source_id, record, _anchor_id = _a_claim(env, workspace_root)
    assert load_source(env.session, source_id) is not None

    moved = attest(
        env.session.connection(),
        record.evidence_id,
        user_id="the-reader",
        note="I read it against the address.",
        checked_at=_MOMENT,
    )

    assert moved.status is VerificationStatus.USER_ATTESTED


# --------------------------------------------------------------------------- #
# the source is gone
# --------------------------------------------------------------------------- #


def test_a_missing_source_refuses_the_store_attestation_and_names_it(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A source the ledger no longer holds may not be attested, and is named.

    The store owns the rule, so the refusal is the store's: a
    :class:`DanglingSourceError` whose message names the source, leaving the
    record ``extracted``. **What would make this red.** Removing the C1 call at
    the attestation -- the behaviour the 2026-11-26 record measured -- would
    advance the record and this would fail.
    """
    context, source_id, record, anchor_id = _a_claim(env, workspace_root)
    _take_the_source_back(context, source_id)
    assert load_source(env.session, source_id) is None

    with pytest.raises(DanglingSourceError) as caught:
        attest(
            env.session.connection(),
            record.evidence_id,
            user_id="the-reader",
            note="I read it against the address.",
            checked_at=_MOMENT,
        )

    assert source_id in str(caught.value), (
        "the refusal names the source whose bytes could not be observed"
    )
    still = load_record(env.session.connection(), record.evidence_id)
    assert still is not None and still.status is VerificationStatus.EXTRACTED, (
        "a refused attestation leaves the record where it was -- not citable"
    )
    anchor = load_anchor(env.session.connection(), anchor_id)
    assert anchor is not None and anchor.source_id == source_id, (
        "the anchor is still in the ledger, so the refusal is C1's and not the "
        "removal having taken the record with the row"
    )


# --------------------------------------------------------------------------- #
# the source is present, its bytes moved
# --------------------------------------------------------------------------- #


def test_a_moved_source_refuses_the_store_attestation_and_names_it(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A source whose current hash no longer matches the anchor is not citable.

    ADR-0004 A2/I4: the address is right and the bytes are not, and the record
    is invalidated rather than refreshed. The source row is present -- so this
    is not the missing-source case -- but its content hash has moved, and the
    attestation refuses and names it.
    """
    _context, source_id, record, _anchor_id = _a_claim(env, workspace_root)
    _move_the_bytes_under_the_source(env, source_id)
    assert load_source(env.session, source_id) is not None, (
        "the source is present; only its bytes moved, so this is drift, not loss"
    )

    with pytest.raises(DanglingSourceError) as caught:
        attest(
            env.session.connection(),
            record.evidence_id,
            user_id="the-reader",
            note="I read it against the address.",
            checked_at=_MOMENT,
        )

    assert source_id in str(caught.value)
    still = load_record(env.session.connection(), record.evidence_id)
    assert still is not None and still.status is VerificationStatus.EXTRACTED


# --------------------------------------------------------------------------- #
# the application maps the refusal onto its own code
# --------------------------------------------------------------------------- #


def test_the_application_refuses_with_its_own_code(env: StoreEnv, workspace_root: Path) -> None:
    """``attest_claim`` carries the store's refusal to the surface as a code.

    The store owns the rule; the application maps it onto
    ``CITATION_SOURCE_UNOBSERVABLE`` so the CLI and the API -- which render an
    :class:`ApplicationRefusedError` the same way -- inherit one answer with a
    machine-readable reason and a message that names the source.
    """
    context, source_id, record, _anchor_id = _a_claim(env, workspace_root)
    _take_the_source_back(context, source_id)

    with pytest.raises(ApplicationRefusedError) as caught:
        attest_claim(
            context,
            record.evidence_id,
            user_id="the-reader",
            note="I read it against the address.",
            now=_MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.CITATION_SOURCE_UNOBSERVABLE
    assert source_id in str(caught.value)
    still = load_record(env.session.connection(), record.evidence_id)
    assert still is not None and still.status is VerificationStatus.EXTRACTED


# --------------------------------------------------------------------------- #
# the surface inherits the answer
# --------------------------------------------------------------------------- #


def test_the_cli_refuses_with_the_reason_and_the_source_named(
    tmp_path: Path,
) -> None:
    """The console script is reached, and it refuses the way the layer does.

    **The layer's answer is the surface's answer.** The rule lives in the
    store, so a surface that renders an
    :class:`~labcairn.application.refusal.ApplicationRefusedError` inherits
    it without spelling anything of its own -- but *inheriting* is a claim
    about the rendering, and this file witnesses it rather than assuming it:
    the command exits with the refusal code, the machine-readable reason is
    the layer's own, and the message names the source the ledger dropped.

    **The whole path is driven from the console script**, so the claim is
    about what a person types: record a claim, take the source back with
    ``sources remove``, then attest. Nothing is written on the way out.
    """
    from test_cli_support import run_cli

    workspace = tmp_path / "workspace"
    assert run_cli("--workspace", str(workspace), "init").returncode == 0
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Read the literature",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert created.returncode == 0, created.stderr

    materials = workspace / "materials"
    materials.mkdir(exist_ok=True)
    (materials / "one.csv").write_text("name,role\n4.2,control\n", encoding="utf-8")
    ingested = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert ingested.returncode == 0, ingested.stderr
    source_id = str(ingested.json()["source_ids"][0])

    addressed = run_cli(
        "--workspace", str(workspace), "sources", "addresses", "--source", source_id, "--json"
    )
    assert addressed.returncode == 0, addressed.stderr
    address = next(item for item in addressed.json() if item["text"].strip() == "4.2")

    claimed = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim",
        "--source",
        source_id,
        "--address",
        address["locator_key"],
        "--kind",
        "numeric",
        "--value",
        "4.2",
        "--unit",
        "dimensionless",
        "--json",
    )
    assert claimed.returncode == 0, claimed.stderr
    evidence_id = str(claimed.json()["record"]["evidence_id"])

    removed = run_cli(
        "--workspace", str(workspace), "sources", "remove", "--source", source_id, "--json"
    )
    assert removed.returncode == 0, removed.stderr

    refused = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim-attest",
        evidence_id,
        "--user",
        "the-advisor",
        "--note",
        "I read it against the table.",
        "--json",
    )

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == ApplicationRefusal.CITATION_SOURCE_UNOBSERVABLE.value
    assert source_id in payload["message"]
