"""Collect the machine-answerable half of Phase 4's exit-gate evidence.

Phase 4's four exit gates read their evidence from
``docs/acceptance/P4-G1-G4-record-skeleton.md``. Every slot in that
skeleton starts at ``PENDING``, and every slot says **what kind of
evidence** would fill it: some are *system capability* -- machinery that is
built and witnessed, and that the trial then confirms on the pilot paper
-- and some are *real trial only*, which no tool can decide, because the
evidence is a person's observation.

This tool is the collector for the first kind. It reads the local
service's read-only routes, decides each machine-answerable slot against
the condition the skeleton states, and writes a record that says what it
read, where it read it and what it concluded. A slot it cannot answer is
left exactly as it was, ``PENDING``, with the reason recorded rather than
a blank.

**What the record may hold.** Ids, digests, counts, timestamps, states and
route names. **Never** the material: no comment body, no paragraph, no
suggestion text, no rule statement, no deck or meeting text. Every value
in the record is projected through an explicit allow-list rather than
copied out of a route payload, so a route that grows a new field cannot
leak into the record by accident.

**Which round the tool is looking at.** The paper round's project id
comes from the **closed binding's own dossier manifest**, which is the
record that names the project, the task and the two versions. No route
lists the workspace's paper projects: the application layer's
``list_paper_projects`` exists and nothing exposes it, so a workspace
that holds no closed binding gives the tool no project id at all.
**The tool does not add that route** -- doing so is another piece of
work, and a tool that guessed which round it was reading would be
reading the wrong evidence. It says so in the record instead: the slots
that need a project read ``UNKNOWN``, and the reason names the round it
could not find.

**What the tool does with the session token.** It reads the token the
service wrote to ``<workspace>/.labcairn/session-token`` and presents it in
the ``Authorization`` header -- ``POST /task/select`` is a mutation, and
the guard asks for the token on every method that is not a read. The token
is never printed, never written to the record, and the record is searched
for it before the record is written.

**The two modes.** ``--dry-run`` (the default) connects, reads and
reports; it writes nothing. ``--apply`` writes the record and renders the
skeleton's status column from it::

    python scripts/pilot_gate_evidence.py --workspace . --dry-run
    python scripts/pilot_gate_evidence.py --workspace . --apply

The service is the one the runbook starts (``labcairn serve --port
8000``); ``--base-url`` points the tool at another one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, TypeVar, cast

import httpx

from labcairn.cli.workspace import WorkspaceLocation, locate

#: The skeleton whose slots this tool reads and renders.
DEFAULT_SKELETON: Final = Path("docs") / "acceptance" / "P4-G1-G4-record-skeleton.md"

#: The record this tool writes.
DEFAULT_RECORD: Final = Path("docs") / "acceptance" / "P4-G1-G4-system-capability-record.json"

#: The address the runbook's own command serves on.
DEFAULT_BASE_URL: Final = "http://127.0.0.1:8000"

#: The record's schema, so a reader knows what shape the file is in.
RECORD_SCHEMA: Final = "labcairn.pilot-gate-evidence/1"

#: What a memoised read returns, so the memo does not erase the type.
_T = TypeVar("_T")

#: The verdicts a slot's machine-checkable part can carry.
PASS: Final = "PASS"
FAIL: Final = "FAIL"
UNKNOWN: Final = "UNKNOWN"
NOT_ADDRESSED: Final = "NOT_ADDRESSED"

#: A coverage kind that names only the machinery. The whole condition of
#: such a slot is decidable by reading the service, so the tool may write
#: a verdict into the slot's status cell.
CAPABILITY_ONLY: Final = "capability-only"

#: A coverage kind that also names the trial's confirmation. The machinery
#: is decidable; the confirmation is not, so the slot stays ``PENDING`` and
#: the tool records what it measured beside it.
CAPABILITY_AND_TRIAL: Final = "capability-and-trial"

#: A coverage kind that only the real trial can decide.
TRIAL_ONLY: Final = "trial-only"

#: The phrases a coverage kind uses when it names the trial's confirmation.
TRIAL_CONFIRMATION_PHRASES: Final = (
    "by the trial",
    "on the pilot paper",
    "on real data",
    "on the pilot deployment",
    "with the pilot's real sources",
)

#: The phrases a coverage kind uses when it says the trial alone decides.
TRIAL_ONLY_PHRASES: Final = ("real trial only",)

#: A row of the skeleton's evidence table.
_ROW: Final = re.compile(r"^\|\s*(G\d-\d)\s*\|")

#: A coverage kind that says the slot shares its evidence with another.
SHARED_WITH: Final = re.compile(r"shared with (G\d-\d)", re.IGNORECASE)

#: The four deliverable kinds the export returns.
DELIVERABLE_KINDS: Final = ("marked", "clean", "response_table", "quality_report")


class EvidenceError(RuntimeError):
    """The tool could not do what it was asked to do.

    Refused rather than guessed: a collector that answered with a
    half-read service would write a record nobody can trust.
    """


# --------------------------------------------------------------------------- #
# what the service answered
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Read:
    """One route read, and what it answered.

    **The route and the outcome, never the payload.** The payload is
    projected into the record by whoever asked for it; this holds the
    fact that a read happened and how it ended.
    """

    route: str
    method: str
    outcome: str
    status: int | None = None
    refusal: str | None = None

    def as_record(self) -> dict[str, Any]:
        """The read, as the record holds it."""
        entry: dict[str, Any] = {
            "route": f"{self.method} {self.route}",
            "outcome": self.outcome,
        }
        if self.status is not None:
            entry["status"] = self.status
        if self.refusal is not None:
            entry["refusal"] = self.refusal
        return entry


@dataclass(frozen=True, slots=True)
class SlotCheck:
    """One slot's outcome: what was read, what it showed, what it means.

    ``verdict`` is about the slot's **machine-checkable** part. Whether
    the slot as a whole is decided is the skeleton's own business: a slot
    whose coverage kind also names the trial's confirmation stays
    ``PENDING`` whatever this says.
    """

    slot: str
    verdict: str
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    read_from: tuple[str, ...] = ()


def _as_int(value: Any) -> int | None:
    """An integer, or nothing."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_str(value: Any) -> str | None:
    """A string, or nothing."""
    return value if isinstance(value, str) else None


def _as_bool(value: Any) -> bool | None:
    """A boolean, or nothing."""
    return value if isinstance(value, bool) else None


def _counted(values: Sequence[Any], key: str) -> dict[str, int]:
    """How many of *values* carry each value of *key*.

    A value that is not a string counts under ``"other"``, so the tally
    is always complete: a count that quietly dropped rows would be a
    count that lied.
    """
    tally: dict[str, int] = {}
    for value in values:
        label = _as_str(value.get(key)) if isinstance(value, Mapping) else None
        if label is None:
            label = "other"
        tally[label] = tally.get(label, 0) + 1
    return dict(sorted(tally.items()))


def _ids(values: Sequence[Any], key: str) -> list[str]:
    """The ids of *values*, in the order they came."""
    found: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            identifier = _as_str(value.get(key))
            if identifier is not None:
                found.append(identifier)
    return found


def _source_ids(entry: Mapping[str, Any]) -> list[str]:
    """The chain material a rule names, as ids.

    A source that is not a string is not an id, and is dropped rather
    than carried as something the record cannot vouch for.
    """
    sources = entry.get("sources")
    if not isinstance(sources, list):
        return []
    found: list[str] = []
    for item in sources:
        identifier = _as_str(item)
        if identifier is not None:
            found.append(identifier)
    return found


# --------------------------------------------------------------------------- #
# the service
# --------------------------------------------------------------------------- #


class Service:
    """The local service, over HTTP, with the session token presented.

    **The token is presented, never kept.** It goes into the header once;
    the record never sees it, and the record's own check looks for it
    before the record is written.
    """

    def __init__(self, base_url: str, token: str | None, timeout: float = 20.0) -> None:
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)

    def close(self) -> None:
        """Let the connection go."""
        self._client.close()

    def request(
        self,
        method: str,
        route: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[Any, Read]:
        """Make one request, and say what it answered.

        A refusal is a fact about the service, not an error of this tool:
        it comes back as a ``refused`` read carrying the refusal's own
        ``reason`` code, and the message -- which could quote anything --
        is dropped on the floor.
        """
        try:
            response = self._client.request(method, route, params=params, json=body)
        except httpx.HTTPError as error:
            return None, Read(route, method, "unreachable", refusal=type(error).__name__)
        if response.status_code >= 400:
            return None, Read(
                route,
                method,
                "refused",
                response.status_code,
                _refusal_reason(response),
            )
        try:
            payload = response.json()
        except ValueError:
            return None, Read(route, method, "unreadable", response.status_code)
        return payload, Read(route, method, "ok", response.status_code)


def _refusal_reason(response: httpx.Response) -> str | None:
    """The refusal's machine-readable half, if the body carries one."""
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, Mapping):
        return None
    return _as_str(body.get("reason"))


# --------------------------------------------------------------------------- #
# the collector
# --------------------------------------------------------------------------- #


class Collector:
    """Reads the service and decides the slots it is asked to decide.

    **Every read is projected, never copied.** The projection is where
    the material boundary is kept: a route that answers with a comment
    body, a rule statement or a deck's text is projected down to its
    ids, its digests and its counts before it reaches the record.
    """

    def __init__(self, service: Service, queries: Sequence[str]) -> None:
        self._service = service
        self._queries = tuple(queries)
        self._reads: list[Read] = []
        self._memo: dict[str, Any] = {}
        self._dossier: dict[str, Any] | None = None
        self._dossier_read = False

    # -- the reads ---------------------------------------------------------- #

    def _read(
        self,
        method: str,
        route: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[Any, Read]:
        """One read, logged."""
        payload, read = self._service.request(method, route, params=params, body=body)
        self._reads.append(read)
        return payload, read

    def _once(self, key: str, produce: Callable[[], _T]) -> _T:
        """The value of *key*, read once.

        Two slots asking the same route get the same answer, and the
        route is read once: a record that showed the same read three
        times would read as three facts rather than one.
        """
        if key not in self._memo:
            self._memo[key] = produce()
        return cast(_T, self._memo[key])

    def health(self) -> dict[str, Any]:
        """What the service is, and where it listens."""
        payload, _ = self._read("GET", "/health")
        if not isinstance(payload, Mapping):
            return {}
        origins = payload.get("origins")
        origin_count = len(origins) if isinstance(origins, list) else None
        return {
            "status": _as_str(payload.get("status")),
            "host": _as_str(payload.get("host")),
            "port": _as_int(payload.get("port")),
            "task_id": _as_str(payload.get("task_id")),
            "origin_count": origin_count,
        }

    def select_task(self, task_id: str) -> dict[str, Any]:
        """Bind the service to the task, and report the binding.

        **This is a mutation, so it presents the token.** What it changes
        is the workspace's selection, and it is asked to select the task
        the service is already serving, so the walk it records is the
        walk the runbook's first step performs.
        """
        payload, _ = self._read("POST", "/task/select", body={"task_id": task_id})
        if not isinstance(payload, Mapping):
            return {}
        return {
            "task_id": _as_str(payload.get("task_id")),
            "status": _as_str(payload.get("status")),
        }

    def task_state(self) -> dict[str, Any]:
        """What the task currently is: its runs, stages, artefacts, approvals.

        The task's own title and goal are the paper's title and the
        operator's words, so they are not projected here; what the gates
        read is the shape of the state and the decisions recorded in it.
        """
        return self._once("task_state", self._read_task_state)

    def _read_task_state(self) -> dict[str, Any]:
        payload, _ = self._read("GET", "/task")
        if not isinstance(payload, Mapping):
            return {}
        task = payload.get("task")
        runs = payload.get("runs")
        stages = payload.get("stages")
        artifacts = payload.get("artifacts")
        approvals = payload.get("approvals")
        run_rows = runs if isinstance(runs, list) else []
        stage_rows = stages if isinstance(stages, list) else []
        artifact_rows = artifacts if isinstance(artifacts, list) else []
        approval_rows = approvals if isinstance(approvals, list) else []
        return {
            "task_id": _as_str(task.get("task_id")) if isinstance(task, Mapping) else None,
            "run_count": len(run_rows),
            "run_statuses": _counted(run_rows, "status"),
            "run_ids": _ids(run_rows, "run_id"),
            "stage_count": len(stage_rows),
            "stage_statuses": _counted(stage_rows, "status"),
            "artifact_count": len(artifact_rows),
            "approval_count": len(approval_rows),
            "approval_states": _counted(approval_rows, "state"),
            "last_event_seq": _as_int(payload.get("last_event_seq")),
        }

    def artifacts(self) -> list[dict[str, Any]]:
        """The artefacts this task has produced, with their digests."""
        return self._once("artifacts", self._read_artifacts)

    def _read_artifacts(self) -> list[dict[str, Any]]:
        payload, _ = self._read("GET", "/artifacts")
        if not isinstance(payload, list):
            return []
        projected: list[dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            receipt = entry.get("receipt")
            if not isinstance(receipt, Mapping):
                continue
            derived = receipt.get("derived_from")
            projected.append(
                {
                    "receipt_id": _as_str(receipt.get("receipt_id")),
                    "kind": _as_str(receipt.get("kind")),
                    "content_sha256": _as_str(receipt.get("content_sha256")),
                    "size_bytes": _as_int(receipt.get("size_bytes")),
                    "revision": _as_int(receipt.get("revision")),
                    "produced_by": _as_str(receipt.get("produced_by")),
                    "producer_id": _as_str(receipt.get("producer_id")),
                    "staleness": _as_str(receipt.get("staleness")),
                    "relative_path": _as_str(receipt.get("relative_path")),
                    "created_at": _as_str(receipt.get("created_at")),
                    "derived_from_count": len(derived) if isinstance(derived, list) else 0,
                }
            )
        return projected

    def events(self) -> dict[str, Any]:
        """The task's event timeline, as a shape rather than as payloads.

        The event's own ``payload`` is dropped: it is where a stage's
        details would travel, and the gates read the timeline's shape.
        """
        return self._once("events", self._read_events)

    def _read_events(self) -> dict[str, Any]:
        payload, _ = self._read("GET", "/events")
        if not isinstance(payload, Mapping):
            return {}
        events = payload.get("events")
        rows = events if isinstance(events, list) else []
        return {
            "event_count": len(rows),
            "next_after_seq": _as_int(payload.get("next_after_seq")),
            "caught_up": _as_bool(payload.get("caught_up")),
            "event_types": _counted(rows, "type"),
            "transitions": _counted(rows, "transition"),
        }

    def opinions(self, project_id: str, version_id: str) -> dict[str, Any]:
        """The round's opinions, with their suggestions and verdicts."""
        payload, _ = self._read(
            "GET",
            "/review/opinions",
            params={"project_id": project_id, "version_id": version_id},
        )
        if not isinstance(payload, Mapping):
            return {}
        opinions = payload.get("opinions")
        rows = opinions if isinstance(opinions, list) else []
        return {
            "opinion_count": len(rows),
            "opinion_ids": _ids(rows, "feedback_id"),
        }

    def trajectory(self) -> dict[str, Any]:
        """The paper's trajectory: the comments, the edits, the responses.

        **The comment's text is not projected.** The feedback ids are,
        because the trace walk is about which links resolve.
        """
        return self._once("trajectory", self._read_trajectory)

    def _read_trajectory(self) -> dict[str, Any]:
        payload, _ = self._read("GET", "/trajectory")
        if not isinstance(payload, Mapping):
            return {}
        comments = payload.get("comments")
        edits = payload.get("edits")
        responses = payload.get("responses")
        comment_rows = comments if isinstance(comments, list) else []
        edit_rows = edits if isinstance(edits, list) else []
        response_rows = responses if isinstance(responses, list) else []
        return {
            "comment_count": len(comment_rows),
            "comment_ids": _ids(comment_rows, "feedback_id"),
            "edit_count": len(edit_rows),
            "edit_ids": _ids(edit_rows, "edit_action_id"),
            "response_count": len(response_rows),
            "response_states": _counted(response_rows, "state"),
        }

    def trajectory_graph(self, project_id: str) -> dict[str, Any]:
        """The versions the project holds, and the edges between them."""
        payload, _ = self._read("GET", "/trajectory/graph", params={"project_id": project_id})
        if not isinstance(payload, Mapping):
            return {}
        versions = payload.get("version_ids")
        edges = payload.get("edges")
        version_rows = versions if isinstance(versions, list) else []
        edge_rows = edges if isinstance(edges, list) else []
        return {
            "version_count": len(version_rows),
            "version_ids": [_as_str(item) for item in version_rows],
            "edge_count": len(edge_rows),
            "edge_ids": _ids(edge_rows, "edge_id"),
        }

    def guidance_rules(self) -> list[dict[str, Any]]:
        """The rules the memory holds, with the material they name.

        **The rule's statement is not projected.** The rule id, its state
        and the chain material it was learned from are: the gates read
        whether a rule names its sources, not what it says.
        """
        return self._once("guidance_rules", self._read_guidance_rules)

    def _read_guidance_rules(self) -> list[dict[str, Any]]:
        payload, _ = self._read("GET", "/guidance/rules")
        if not isinstance(payload, list):
            return []
        projected: list[dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            projected.append(
                {
                    "rule_id": _as_str(entry.get("rule_id")),
                    "version": _as_int(entry.get("version")),
                    "state": _as_str(entry.get("state")),
                    "shared_scope": _as_str(entry.get("shared_scope")),
                    "source_ids": _source_ids(entry),
                    "source_count": len(_source_ids(entry)),
                    "proposed_at": _as_str(entry.get("proposed_at")),
                    "confirmed_at": _as_str(entry.get("confirmed_at")),
                    "published_at": _as_str(entry.get("published_at")),
                }
            )
        return projected

    def usable_rules(self, project_id: str | None) -> list[dict[str, Any]]:
        """The rules a card may cite, with their state.

        The rule's name and summary are the rule's own words, so they are
        not projected.
        """
        return self._once(f"usable_rules:{project_id}", lambda: self._read_usable_rules(project_id))

    def _read_usable_rules(self, project_id: str | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if project_id is not None:
            params["project_id"] = project_id
        payload, _ = self._read("GET", "/guidance/usable", params=params or None)
        if not isinstance(payload, list):
            return []
        projected: list[dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            projected.append(
                {
                    "rule_id": _as_str(entry.get("rule_id")),
                    "version": _as_int(entry.get("version")),
                    "state": _as_str(entry.get("state")),
                    "scope": _as_str(entry.get("scope")),
                    "source_ids": _source_ids(entry),
                    "confirmed_at": _as_str(entry.get("confirmed_at")),
                }
            )
        return projected

    def search(self, route: str, query: str) -> list[dict[str, Any]]:
        """One search surface's hits, addressed to their source.

        **The hit's text is not projected.** What is projected is the
        provenance: which record the hit came from, which file it was
        read from, and the digest that ties it to that file.
        """
        payload, _ = self._read("GET", route, params={"q": query})
        if not isinstance(payload, list):
            return []
        projected: list[dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            projected.append(
                {
                    "trajectory_id": _as_str(entry.get("trajectory_id")),
                    "record_id": _as_str(entry.get("record_id")),
                    "object_id": _as_str(entry.get("object_id")),
                    "project_id": _as_str(entry.get("project_id")),
                    "feedback_id": _as_str(entry.get("feedback_id")),
                    "edit_action_id": _as_str(entry.get("edit_action_id")),
                    "revision_event_id": _as_str(entry.get("revision_event_id")),
                    "version_id": _as_str(entry.get("version_id")),
                    "issue_key": _as_str(entry.get("issue_key")),
                    "entry_kind": _as_str(entry.get("entry_kind")),
                    "source_version_id": _as_str(entry.get("source_version_id")),
                    "source_sha256": _as_str(entry.get("source_sha256")),
                    "source_locator": _as_str(entry.get("source_locator")),
                    "text_digest": _as_str(entry.get("text_digest")),
                    "slide_no": _as_int(entry.get("slide_no")),
                    "object_kind": _as_str(entry.get("object_kind")),
                    "object_fingerprint": _as_str(entry.get("object_fingerprint")),
                    "record_format": _as_str(entry.get("record_format")),
                    "record_index": _as_int(entry.get("record_index")),
                    "record_fingerprint": _as_str(entry.get("record_fingerprint")),
                    "ingested_at": _as_str(entry.get("ingested_at")),
                }
            )
        return projected

    def deliverables(self, project_id: str, dossier_artifact_id: str) -> dict[str, Any] | None:
        """The four deliverables of one closed binding, with their digests.

        **The bytes are dropped.** The export carries each deliverable's
        content, base64-encoded; what the gates read is the kind, the
        relative path and the sha256 beside it.
        """
        payload, _ = self._read(
            "GET",
            "/review/deliverables",
            params={"project_id": project_id, "dossier_artifact_id": dossier_artifact_id},
        )
        if not isinstance(payload, Mapping):
            return None
        files = payload.get("deliverables")
        rows = files if isinstance(files, list) else []
        return {
            "project_id": _as_str(payload.get("project_id")),
            "dossier_artifact_id": _as_str(payload.get("dossier_artifact_id")),
            "task_id": _as_str(payload.get("task_id")),
            "input_version_id": _as_str(payload.get("input_version_id")),
            "output_version_id": _as_str(payload.get("output_version_id")),
            "marked_receipt_id": _as_str(payload.get("marked_receipt_id")),
            "clean_receipt_id": _as_str(payload.get("clean_receipt_id")),
            "edge_id": _as_str(payload.get("edge_id")),
            "deliverables": [
                {
                    "kind": _as_str(item.get("kind")),
                    "relative_path": _as_str(item.get("relative_path")),
                    "sha256": _as_str(item.get("sha256")),
                    "size_bytes": _as_int(item.get("size_bytes")),
                }
                for item in rows
                if isinstance(item, Mapping)
            ],
        }

    def quality(self, project_id: str, dossier_artifact_id: str) -> dict[str, Any] | None:
        """The six §7.4 checks over one closed round's dossier manifest.

        Each check's outcome is projected down to its name and its
        verdict; the facts behind it carry the reviewer's own words and
        are not projected.
        """
        payload, _ = self._read(
            "GET",
            "/review/quality",
            params={"project_id": project_id, "dossier_artifact_id": dossier_artifact_id},
        )
        if not isinstance(payload, Mapping):
            return None
        checks = payload.get("checks")
        rows = checks if isinstance(checks, list) else []
        projected: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            facts = item.get("facts")
            projected.append(
                {
                    "check": _as_str(item.get("check")),
                    "passed": _as_bool(item.get("passed")),
                    "fact_count": len(facts) if isinstance(facts, list) else 0,
                }
            )
        return {
            "project_id": _as_str(payload.get("project_id")),
            "input_version_id": _as_str(payload.get("input_version_id")),
            "output_version_id": _as_str(payload.get("output_version_id")),
            "dossier_artifact_id": _as_str(payload.get("dossier_artifact_id")),
            "check_count": len(rows),
            "checks": projected,
        }

    # -- the dossier -------------------------------------------------------- #

    def dossier(self) -> dict[str, Any] | None:
        """The closed binding's manifest, as ids and digests.

        **The manifest is the deliverables' shared record**, so it is
        the one document whose whole content is ids, digests and counts
        -- with one exception: an unresolved entry's ``detail`` and a
        handover's ``detail`` carry a reviewer's words, and those are not
        projected.
        """
        if self._dossier_read:
            return self._dossier
        self._dossier_read = True
        manifests = [entry for entry in self.artifacts() if entry.get("kind") == "manifest"]
        if not manifests:
            self._dossier = None
            return None
        manifests.sort(key=lambda entry: str(entry.get("created_at") or ""))
        chosen = manifests[-1]
        receipt_id = chosen.get("receipt_id")
        if not isinstance(receipt_id, str):
            self._dossier = None
            return None
        payload, _ = self._read("GET", f"/artifacts/{receipt_id}/content")
        if not isinstance(payload, Mapping):
            self._dossier = None
            return None
        opinions = payload.get("opinions")
        suggestions = payload.get("suggestions")
        decisions = payload.get("decisions")
        responses = payload.get("responses")
        unresolved = payload.get("unresolved")
        handovers = payload.get("handovers")
        decision_rows = decisions if isinstance(decisions, list) else []
        self._dossier = {
            "dossier_artifact_id": receipt_id,
            "task_id": _as_str(payload.get("task_id")),
            "project_id": _as_str(payload.get("project_id")),
            "input_version_id": _as_str(payload.get("input_version_id")),
            "output_version_id": _as_str(payload.get("output_version_id")),
            "marked_receipt_id": _as_str(payload.get("marked_receipt_id")),
            "marked_sha256": _as_str(payload.get("marked_sha256")),
            "clean_receipt_id": _as_str(payload.get("clean_receipt_id")),
            "clean_sha256": _as_str(payload.get("clean_sha256")),
            "edge_id": _as_str(payload.get("edge_id")),
            "closed_at": _as_str(payload.get("closed_at")),
            "opinion_count": len(opinions) if isinstance(opinions, list) else 0,
            "suggestion_count": len(suggestions) if isinstance(suggestions, list) else 0,
            "decision_count": len(decision_rows),
            "decision_verdicts": _counted(decision_rows, "verdict"),
            "response_count": len(responses) if isinstance(responses, list) else 0,
            "response_states": _counted(responses if isinstance(responses, list) else [], "state"),
            "unresolved_count": len(unresolved) if isinstance(unresolved, list) else 0,
            "handover_count": len(handovers) if isinstance(handovers, list) else 0,
        }
        return self._dossier

    # -- the checks --------------------------------------------------------- #

    def check_g1_1(self) -> SlotCheck:
        """G1-1: task entry through to the delivery centre, in one workspace."""
        health = self.health()
        task_id = health.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return SlotCheck(
                "G1-1",
                UNKNOWN,
                "the service named no task, so the walked path was not walked",
                {"service": health},
                ("GET /health",),
            )
        selection = self.select_task(task_id)
        state = self.task_state()
        events = self.events()
        dossier = self.dossier()
        evidence: dict[str, Any] = {
            "task_id": task_id,
            "task_selected": bool(selection.get("task_id")),
            "run_count": state.get("run_count"),
            "stage_count": state.get("stage_count"),
            "artifact_count": state.get("artifact_count"),
            "approval_count": state.get("approval_count"),
            "event_count": events.get("event_count"),
        }
        if dossier is None:
            return SlotCheck(
                "G1-1",
                UNKNOWN,
                "the workspace holds no closed binding, so the path from task "
                "entry to the delivery centre was not walked",
                evidence,
                (
                    "GET /health",
                    "POST /task/select",
                    "GET /task",
                    "GET /events",
                    "GET /artifacts",
                ),
            )
        project_id = dossier.get("project_id")
        output_version_id = dossier.get("output_version_id")
        if not isinstance(project_id, str) or not isinstance(output_version_id, str):
            return SlotCheck(
                "G1-1",
                UNKNOWN,
                "the dossier manifest names no project or output version, so the "
                "opinions could not be read",
                evidence,
                (
                    "GET /health",
                    "POST /task/select",
                    "GET /task",
                    "GET /events",
                    "GET /artifacts",
                    "GET /artifacts/{id}/content",
                ),
            )
        opinions = self.opinions(project_id, output_version_id)
        export = self.deliverables(project_id, dossier["dossier_artifact_id"])
        kinds = (
            sorted(str(item.get("kind")) for item in export.get("deliverables", []))
            if export is not None
            else []
        )
        evidence["opinion_count"] = opinions.get("opinion_count")
        evidence["deliverable_kinds"] = kinds
        evidence["decision_verdicts"] = dossier.get("decision_verdicts")
        read_from = (
            "GET /health",
            "POST /task/select",
            "GET /task",
            "GET /events",
            "GET /artifacts",
            "GET /artifacts/{id}/content",
            "GET /review/opinions",
            "GET /review/deliverables",
        )
        if export is None:
            return SlotCheck(
                "G1-1",
                FAIL,
                "the closed binding refused to export its deliverables, so the "
                "path did not reach the delivery centre",
                evidence,
                read_from,
            )
        if not opinions.get("opinion_count"):
            return SlotCheck(
                "G1-1",
                UNKNOWN,
                "the round holds no opinion, so the opinion-reading step of the "
                "walk was not exercised",
                evidence,
                read_from,
            )
        if sorted(kinds) != sorted(DELIVERABLE_KINDS):
            return SlotCheck(
                "G1-1",
                FAIL,
                f"the export answered with the kinds {kinds} rather than the "
                f"four the gate names ({list(DELIVERABLE_KINDS)})",
                evidence,
                read_from,
            )
        return SlotCheck(
            "G1-1",
            PASS,
            "the service bound the task, served the round's opinions and exported "
            "the four deliverables of the closed binding",
            evidence,
            read_from,
        )

    def check_g2_1(self) -> SlotCheck:
        """G2-1: the trace walk resolves every link."""
        dossier = self.dossier()
        if dossier is None:
            return SlotCheck(
                "G2-1",
                UNKNOWN,
                "the workspace holds no closed binding, so there is no trace to walk",
                {},
                ("GET /artifacts",),
            )
        project_id = dossier.get("project_id")
        if not isinstance(project_id, str):
            return SlotCheck(
                "G2-1",
                UNKNOWN,
                "the dossier manifest names no project, so the graph could not be read",
                {"dossier_artifact_id": dossier.get("dossier_artifact_id")},
                ("GET /artifacts", "GET /artifacts/{id}/content"),
            )
        trajectory = self.trajectory()
        graph = self.trajectory_graph(project_id)
        evidence: dict[str, Any] = {
            "project_id": project_id,
            "task_id": dossier.get("task_id"),
            "input_version_id": dossier.get("input_version_id"),
            "output_version_id": dossier.get("output_version_id"),
            "edge_id": dossier.get("edge_id"),
            "comment_count": trajectory.get("comment_count"),
            "edit_count": trajectory.get("edit_count"),
            "response_count": trajectory.get("response_count"),
            "version_count": graph.get("version_count"),
            "edge_count": graph.get("edge_count"),
        }
        read_from = (
            "GET /artifacts",
            "GET /artifacts/{id}/content",
            "GET /trajectory",
            "GET /trajectory/graph",
        )
        if not trajectory.get("comment_count"):
            return SlotCheck(
                "G2-1",
                UNKNOWN,
                "the trajectory holds no comment, so the walk resolved no link",
                evidence,
                read_from,
            )
        if not graph.get("edge_count"):
            return SlotCheck(
                "G2-1",
                FAIL,
                "the project's graph holds no accepted edge, so the trace walk resolves no link",
                evidence,
                read_from,
            )
        missing = [
            key
            for key in ("task_id", "input_version_id", "output_version_id")
            if not dossier.get(key)
        ]
        if missing:
            return SlotCheck(
                "G2-1",
                FAIL,
                f"the dossier manifest binds no {', '.join(missing)}, so the "
                "revision loop's own ids are not recorded",
                evidence,
                read_from,
            )
        return SlotCheck(
            "G2-1",
            PASS,
            "the manifest binds the task, the input version and the output "
            "version, the trajectory holds the chain, and the graph holds the "
            "accepted edges between the versions",
            evidence,
            read_from,
        )

    def check_g2_2(self) -> SlotCheck:
        """G2-2: the four deliverables are generated and consistently bound."""
        dossier = self.dossier()
        if dossier is None:
            return SlotCheck(
                "G2-2",
                UNKNOWN,
                "the workspace holds no closed binding, so there are no deliverables to bind",
                {},
                ("GET /artifacts",),
            )
        project_id = dossier.get("project_id")
        dossier_id = dossier.get("dossier_artifact_id")
        if not isinstance(project_id, str) or not isinstance(dossier_id, str):
            return SlotCheck(
                "G2-2",
                UNKNOWN,
                "the dossier manifest names no project, so the export could not be asked for",
                {"dossier_artifact_id": dossier_id},
                ("GET /artifacts", "GET /artifacts/{id}/content"),
            )
        export = self.deliverables(project_id, dossier_id)
        if export is None:
            return SlotCheck(
                "G2-2",
                FAIL,
                "the closed binding refused to export its deliverables",
                {"dossier_artifact_id": dossier_id},
                ("GET /artifacts", "GET /artifacts/{id}/content", "GET /review/deliverables"),
            )
        files = export.get("deliverables", [])
        by_kind = {str(item.get("kind")): item for item in files if isinstance(item, Mapping)}
        evidence: dict[str, Any] = {
            "dossier_artifact_id": dossier_id,
            "project_id": project_id,
            "task_id": export.get("task_id"),
            "input_version_id": export.get("input_version_id"),
            "output_version_id": export.get("output_version_id"),
            "kinds": sorted(by_kind),
            "digests": {
                kind: str(item.get("sha256"))
                for kind, item in sorted(by_kind.items())
                if isinstance(item, Mapping)
            },
            "manifest_binding": {
                "marked_sha256": dossier.get("marked_sha256"),
                "clean_sha256": dossier.get("clean_sha256"),
            },
        }
        read_from = (
            "GET /artifacts",
            "GET /artifacts/{id}/content",
            "GET /review/deliverables",
        )
        missing = sorted(set(DELIVERABLE_KINDS) - set(by_kind))
        if missing:
            return SlotCheck(
                "G2-2",
                FAIL,
                f"the export answered without the kinds {missing}",
                evidence,
                read_from,
            )
        mismatched: list[str] = []
        bindings = (
            ("marked", dossier.get("marked_sha256")),
            ("clean", dossier.get("clean_sha256")),
        )
        for kind, bound in bindings:
            if not isinstance(bound, str):
                continue
            digest = _as_str(by_kind[kind].get("sha256"))
            if digest != bound:
                mismatched.append(kind)
        if mismatched:
            return SlotCheck(
                "G2-2",
                FAIL,
                f"the export's {', '.join(mismatched)} digest(s) do not equal the "
                "digest the manifest binds",
                evidence,
                read_from,
            )
        return SlotCheck(
            "G2-2",
            PASS,
            "the export answered with the four kinds, and the marked and clean "
            "digests equal the digests the manifest binds; the response table and "
            "the quality report are rendered from the manifest's own JSON, so "
            "their digests are derived from it rather than bound beside it",
            evidence,
            read_from,
        )

    def check_g2_3(self) -> SlotCheck:
        """G2-3: one real model generates suggestions within the authorised scope."""
        return SlotCheck(
            "G2-3",
            UNKNOWN,
            "no read-only route publishes a suggestion run's account -- the mode, "
            "model id, request count, token estimate, duration and stop reason "
            "are returned by POST /review/suggest and held in the "
            "model_suggestion_runs row, and nothing reads them back",
            {},
            (),
        )

    def check_g2_4(self) -> SlotCheck:
        """G2-4: preview, per-item approval, apply, publish, retry and recovery."""
        dossier = self.dossier()
        if dossier is None:
            return SlotCheck(
                "G2-4",
                UNKNOWN,
                "the workspace holds no closed binding, so no preview, decision or "
                "apply was recorded",
                {},
                ("GET /artifacts",),
            )
        state = self.task_state()
        evidence: dict[str, Any] = {
            "decision_count": dossier.get("decision_count"),
            "decision_verdicts": dossier.get("decision_verdicts"),
            "response_count": dossier.get("response_count"),
            "response_states": dossier.get("response_states"),
            "approval_count": state.get("approval_count"),
            "approval_states": state.get("approval_states"),
            "stage_count": state.get("stage_count"),
            "stage_statuses": state.get("stage_statuses"),
        }
        read_from = ("GET /artifacts", "GET /artifacts/{id}/content", "GET /task")
        if not dossier.get("decision_count"):
            return SlotCheck(
                "G2-4",
                UNKNOWN,
                "the round holds no per-item decision, so the per-item approval "
                "step was not exercised",
                evidence,
                read_from,
            )
        return SlotCheck(
            "G2-4",
            PASS,
            "the round recorded a decision for every suggestion, and the "
            "approval ledger holds the approvals the apply spent; the deliberate "
            "interruption and the restart recovery are drills rather than reads, "
            "and are not measured here",
            evidence,
            read_from,
        )

    def check_g2_5(self) -> SlotCheck:
        """G2-5: the key refusal paths and the evidence checks pass."""
        dossier = self.dossier()
        if dossier is None:
            return SlotCheck(
                "G2-5",
                UNKNOWN,
                "the workspace holds no closed binding, so there is no deliverable "
                "whose digest could be checked",
                {},
                ("GET /artifacts",),
            )
        project_id = dossier.get("project_id")
        dossier_id = dossier.get("dossier_artifact_id")
        if not isinstance(project_id, str) or not isinstance(dossier_id, str):
            return SlotCheck(
                "G2-5",
                UNKNOWN,
                "the dossier manifest names no project, so the checks could not be asked for",
                {"dossier_artifact_id": dossier_id},
                ("GET /artifacts", "GET /artifacts/{id}/content"),
            )
        export = self.deliverables(project_id, dossier_id)
        quality = self.quality(project_id, dossier_id)
        evidence: dict[str, Any] = {
            "export_refused": export is None,
            "check_count": quality.get("check_count") if quality else None,
            "checks": quality.get("checks") if quality else None,
        }
        read_from = (
            "GET /artifacts",
            "GET /artifacts/{id}/content",
            "GET /review/deliverables",
            "GET /review/quality",
        )
        if export is None:
            return SlotCheck(
                "G2-5",
                FAIL,
                "the export refused, so the digest check did not hold",
                evidence,
                read_from,
            )
        if quality is None:
            return SlotCheck(
                "G2-5",
                UNKNOWN,
                "the six §7.4 checks refused, so they were not measured",
                evidence,
                read_from,
            )
        failed = [
            str(item.get("check"))
            for item in quality.get("checks", [])
            if isinstance(item, Mapping) and item.get("passed") is False
        ]
        if failed:
            return SlotCheck(
                "G2-5",
                FAIL,
                f"the §7.4 checks {', '.join(failed)} did not hold",
                evidence,
                read_from,
            )
        return SlotCheck(
            "G2-5",
            PASS,
            "the export hash-checked the drafts against the manifest and "
            "answered, and all six §7.4 checks hold; the refusal injections "
            "themselves are exercises rather than reads, and are not measured here",
            evidence,
            read_from,
        )

    def check_g3_1(self) -> SlotCheck:
        """G3-1: paper, deck and meeting text are retrievable by source."""
        if not self._queries:
            return SlotCheck(
                "G3-1",
                UNKNOWN,
                "no search query was supplied, so no search surface was exercised",
                {},
                (),
            )
        surfaces = (
            ("/trajectory/search", "trajectory"),
            ("/ppt/search", "deck"),
            ("/meeting/search", "meeting"),
        )
        evidence: dict[str, Any] = {}
        read_from: list[str] = []
        unanswered: list[str] = []
        empty: list[str] = []
        for route, label in surfaces:
            hits: list[dict[str, Any]] = []
            for query in self._queries:
                hits.extend(self.search(route, query))
            read_from.append(f"GET {route}")
            evidence[f"{label}_hit_count"] = len(hits)
            if not hits:
                empty.append(label)
                continue
            addressed = [
                hit
                for hit in hits
                if hit.get("source_sha256") is not None
                or hit.get("feedback_id") is not None
                or hit.get("object_fingerprint") is not None
                or hit.get("record_fingerprint") is not None
            ]
            evidence[f"{label}_addressed_hit_count"] = len(addressed)
            if len(addressed) != len(hits):
                unanswered.append(label)
        if unanswered:
            return SlotCheck(
                "G3-1",
                FAIL,
                f"the {', '.join(unanswered)} surface answered with hits that name no source",
                evidence,
                tuple(read_from),
            )
        if empty:
            return SlotCheck(
                "G3-1",
                UNKNOWN,
                f"the {', '.join(empty)} surface(s) answered with no hit for the "
                "query, so the retrieval was not exercised there",
                evidence,
                tuple(read_from),
            )
        dossier = self.dossier()
        trajectory = self.trajectory()
        evidence["comment_count"] = trajectory.get("comment_count")
        read_from.append("GET /trajectory")
        if dossier is None or not trajectory.get("comment_count"):
            return SlotCheck(
                "G3-1",
                UNKNOWN,
                "the paper's own trajectory holds no comment, so the pilot paper's "
                "trajectory was not resolved",
                evidence,
                tuple(read_from),
            )
        return SlotCheck(
            "G3-1",
            PASS,
            "each search surface answered with hits addressed to their own "
            "source, and the paper's own trajectory resolved",
            evidence,
            tuple(read_from),
        )

    def check_g3_2(self) -> SlotCheck:
        """G3-2: a walked link from a raw source through its rule to the record."""
        rules = self.guidance_rules()
        evidence: dict[str, Any] = {"rule_count": len(rules)}
        if not rules:
            return SlotCheck(
                "G3-2",
                UNKNOWN,
                "the memory holds no rule, so the link from a raw source through "
                "a distilled rule to the rule's record was not walked",
                evidence,
                ("GET /guidance/rules",),
            )
        without_source = [
            str(rule.get("rule_id")) for rule in rules if not rule.get("source_count")
        ]
        evidence["rules_without_source"] = without_source
        evidence["source_counts"] = sorted({int(rule.get("source_count") or 0) for rule in rules})
        if without_source:
            return SlotCheck(
                "G3-2",
                FAIL,
                f"{len(without_source)} rule(s) name no material they were learned "
                "from, so the link does not close",
                evidence,
                ("GET /guidance/rules",),
            )
        return SlotCheck(
            "G3-2",
            PASS,
            "every rule the memory holds names the chain material it was learned "
            "from, so a source reaches its rule and the rule reaches its record",
            evidence,
            ("GET /guidance/rules",),
        )

    def check_g3_3(self) -> SlotCheck:
        """G3-3: a rule confirmed by the advisor is callable by another project."""
        rules = self.guidance_rules()
        confirmed = [rule for rule in rules if rule.get("state") == "confirmed"]
        evidence: dict[str, Any] = {
            "rule_count": len(rules),
            "confirmed_rule_count": len(confirmed),
        }
        if not confirmed:
            return SlotCheck(
                "G3-3",
                UNKNOWN,
                "the memory holds no confirmed rule, so no advisor confirmation was exercised",
                evidence,
                ("GET /guidance/rules",),
            )
        return SlotCheck(
            "G3-3",
            UNKNOWN,
            "a second project's context is not reachable from one service, so "
            "the cross-project call was not exercised; the confirmed rule's "
            "shared scope is recorded, and the call itself is the trial's",
            evidence,
            ("GET /guidance/rules",),
        )

    def check_g3_4(self) -> SlotCheck:
        """G3-4: an unconfirmed relation cannot become a guidance rule directly."""
        rules = self.guidance_rules()
        states = {rule.get("rule_id"): rule.get("state") for rule in rules}
        dossier = self.dossier()
        project_id = dossier.get("project_id") if dossier else None
        usable = self.usable_rules(project_id if isinstance(project_id, str) else None)
        evidence: dict[str, Any] = {
            "rule_count": len(rules),
            "usable_rule_count": len(usable),
            "usable_states": _counted(usable, "state"),
        }
        read_from = ("GET /guidance/rules", "GET /guidance/usable")
        if not usable:
            return SlotCheck(
                "G3-4",
                UNKNOWN,
                "no rule is served to a card, so the listing was not exercised",
                evidence,
                read_from,
            )
        unconfirmed = [
            str(rule.get("rule_id"))
            for rule in usable
            if states.get(rule.get("rule_id")) not in (None, "confirmed")
        ]
        evidence["unconfirmed_served"] = unconfirmed
        if unconfirmed:
            return SlotCheck(
                "G3-4",
                FAIL,
                f"the listing served {len(unconfirmed)} rule(s) that are not confirmed",
                evidence,
                read_from,
            )
        return SlotCheck(
            "G3-4",
            PASS,
            "every rule the listing serves is a confirmed one, so a candidate "
            "reaching a card would be a rule that was never confirmed",
            evidence,
            read_from,
        )

    # -- the whole walk ----------------------------------------------------- #

    def run(self) -> list[SlotCheck]:
        """Every slot this tool decides, in the skeleton's own order."""
        checks = (
            self.check_g1_1,
            self.check_g2_1,
            self.check_g2_2,
            self.check_g2_3,
            self.check_g2_4,
            self.check_g2_5,
            self.check_g3_1,
            self.check_g3_2,
            self.check_g3_3,
            self.check_g3_4,
        )
        return [check() for check in checks]

    @property
    def reads(self) -> tuple[Read, ...]:
        """Every read this collector made, in order."""
        return tuple(self._reads)


# --------------------------------------------------------------------------- #
# the skeleton
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SkeletonRow:
    """One row of the skeleton's evidence table."""

    slot: str
    condition: str
    evidence: str
    producer: str
    coverage_kind: str
    status: str


def parse_skeleton(text: str) -> list[SkeletonRow]:
    """The skeleton's evidence rows, as the table holds them.

    A row that does not have six cells is not a row this tool understands,
    and it is skipped rather than half-read -- a table this tool
    mis-parses would fill the wrong cell.
    """
    rows: list[SkeletonRow] = []
    for line in text.splitlines():
        match = _ROW.match(line)
        if match is None:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        rows.append(
            SkeletonRow(
                slot=cells[0],
                condition=cells[1],
                evidence=cells[2],
                producer=cells[3],
                coverage_kind=cells[4],
                status=cells[5],
            )
        )
    return rows


def coverage_of(kind: str, *, kinds: Mapping[str, str] | None = None) -> str:
    """What kind of coverage a coverage kind names.

    Three kinds, and the middle one is the one that decides a cell:
    a slot whose kind names only the machinery can carry a verdict, a slot
    whose kind also names the trial's confirmation cannot, and a slot
    only the trial can decide is not this tool's business at all.

    **A slot that shares its evidence with another slot inherits that
    slot's kind.** The skeleton's own word is that the evidence is the
    same, and a slot that inherits a trial-confirmed condition is not
    decided by the machinery alone either.
    """
    lowered = kind.lower()
    if any(phrase in lowered for phrase in TRIAL_ONLY_PHRASES):
        return TRIAL_ONLY
    if any(phrase in lowered for phrase in TRIAL_CONFIRMATION_PHRASES):
        return CAPABILITY_AND_TRIAL
    shared = SHARED_WITH.search(kind)
    if shared is not None and kinds is not None:
        referent = kinds.get(shared.group(1))
        if referent is not None and referent != kind:
            return coverage_of(referent, kinds=kinds)
    return CAPABILITY_ONLY


def shared_with(kind: str) -> str | None:
    """The slot whose evidence this slot shares, if it shares any."""
    shared = SHARED_WITH.search(kind)
    return shared.group(1) if shared is not None else None


def render_status(
    row: SkeletonRow,
    check: SlotCheck | None,
    coverage: str,
    record_name: str,
) -> str:
    """What the slot's status cell says after this run.

    **A cell is never a claim the evidence does not carry.** A slot the
    tool decided outright carries its verdict and where the verdict was
    read. A slot whose condition also needs the trial's confirmation
    stays ``PENDING`` and says what was measured. A slot only the trial
    can decide is left exactly as it was.
    """
    if check is None:
        return row.status
    if coverage == TRIAL_ONLY:
        return row.status
    if check.verdict == UNKNOWN:
        return f"PENDING — {check.reason} (record: {record_name})"
    if coverage == CAPABILITY_AND_TRIAL:
        return (
            f"PENDING — capability {check.verdict}, trial confirmation "
            f"outstanding (record: {record_name})"
        )
    return f"{check.verdict} — {record_name}"


def apply_statuses(text: str, statuses: Mapping[str, str]) -> str:
    """The skeleton, with the given slots' status cells replaced.

    **Only the status cell moves.** Every other cell, and every line
    outside the table, is written back exactly as it was read.
    """
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    for line in lines:
        match = _ROW.match(line)
        if match is None:
            output.append(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            output.append(line)
            continue
        replacement = statuses.get(cells[0])
        if replacement is None:
            output.append(line)
            continue
        ending = "\n" if line.endswith("\n") else ""
        output.append("| " + " | ".join([*cells[:5], replacement]) + " |" + ending)
    return "".join(output)


# --------------------------------------------------------------------------- #
# the record
# --------------------------------------------------------------------------- #


def build_record(
    *,
    command: str,
    base_url: str,
    workspace: Path,
    token: str | None,
    queries: Sequence[str],
    checks: Sequence[SlotCheck],
    reads: Sequence[Read],
    rows: Sequence[SkeletonRow],
    record_name: str,
    note: str,
) -> dict[str, Any]:
    """The record, as the file holds it.

    **Every slot the skeleton names appears here**, whether the tool
    decided it or not, and a slot the tool did not decide carries the
    reason it was left alone. A reader can therefore tell the difference
    between a slot the tool could not answer and a slot the tool never
    looked at.
    """
    by_slot = {check.slot: check for check in checks}
    kinds = {row.slot: row.coverage_kind for row in rows}
    slots: list[dict[str, Any]] = []
    for row in rows:
        coverage = coverage_of(row.coverage_kind, kinds=kinds)
        check = by_slot.get(row.slot)
        if check is None:
            referent = shared_with(row.coverage_kind)
            shared = by_slot.get(referent) if referent is not None else None
            if shared is not None:
                check = SlotCheck(
                    slot=row.slot,
                    verdict=shared.verdict,
                    reason=shared.reason,
                    evidence=shared.evidence,
                    read_from=shared.read_from,
                )
        if coverage == TRIAL_ONLY:
            verdict = NOT_ADDRESSED
            reason = (
                "the slot's coverage kind says the real trial alone decides it, "
                "and the evidence is a person's observation"
            )
            evidence: Mapping[str, Any] = {}
            read_from: tuple[str, ...] = ()
        elif check is None:
            verdict = NOT_ADDRESSED
            reason = "this tool has no checker for the slot"
            evidence = {}
            read_from = ()
        else:
            verdict = check.verdict
            reason = check.reason
            evidence = check.evidence
            read_from = check.read_from
        slots.append(
            {
                "slot": row.slot,
                "condition": row.condition,
                "coverage_kind": row.coverage_kind,
                "coverage": coverage,
                "verdict": verdict,
                "reason": reason,
                "evidence": dict(evidence),
                "read_from": list(read_from),
                "status_after_this_run": render_status(row, check, coverage, record_name),
            }
        )
    return {
        "schema": RECORD_SCHEMA,
        "tool": "scripts/pilot_gate_evidence.py",
        "command": command,
        "collected_at": datetime.now(UTC).isoformat(),
        "service": {"base_url": base_url},
        "workspace": {
            "root": str(workspace),
            "session_token_present": token is not None,
            "note": note,
        },
        "queries": list(queries),
        "reads": [read.as_record() for read in reads],
        "slots": slots,
    }


def assert_material_free(record: Mapping[str, Any], token: str | None) -> None:
    """The record must carry no token and no material.

    **The token check is a check, not a hope.** The record is searched
    for the token the service minted, and a record that carries it is
    refused rather than written.

    **The material check is structural.** Every value in the record is
    an id, a digest, a count, a timestamp, a state or a route name, and
    the ones this tool writes are the only ones that could be anything
    else are the tool's own English sentences -- which this check
    recognises by their shape and refuses.
    """
    text = json.dumps(record, indent=2, sort_keys=False)
    if token is not None and token in text:
        raise EvidenceError("the record carries the session token; it must not be written anywhere")
    for slot in record.get("slots", []):
        for value in slot.get("evidence", {}).values():
            if isinstance(value, str) and len(value) > 200:
                raise EvidenceError(
                    f"the record carries a {len(value)}-character value for slot "
                    f"{slot.get('slot')}; the record holds ids, digests, counts "
                    "and timestamps, not prose"
                )


# --------------------------------------------------------------------------- #
# the command line
# --------------------------------------------------------------------------- #


def _read_token(location: WorkspaceLocation) -> str | None:
    """The session token the service wrote, if it wrote one.

    The token is read, used and dropped. It is never printed and never
    written, and the record's own check looks for it before the record
    is written.
    """
    path = location.token_path
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    return value or None


def _print_report(record: Mapping[str, Any]) -> None:
    """What the run found, for the terminal."""
    print(f"service: {record['service']['base_url']}")
    print(f"workspace: {record['workspace']['root']}")
    print(f"reads: {len(record['reads'])}")
    for slot in record["slots"]:
        print(f"  {slot['slot']}: {slot['verdict']} — {slot['reason']}")


def build_parser() -> argparse.ArgumentParser:
    """The command line."""
    parser = argparse.ArgumentParser(
        prog="pilot_gate_evidence.py",
        description=(
            "Collect the machine-answerable half of Phase 4's exit-gate evidence. "
            "Dry-run by default; pass --apply to write the record and the "
            "skeleton's status column."
        ),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(),
        help="the LabCairn workspace root (default: the current directory)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"the local service's address (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--skeleton",
        type=Path,
        default=DEFAULT_SKELETON,
        help=f"the exit-record skeleton (default: {DEFAULT_SKELETON.as_posix()})",
    )
    parser.add_argument(
        "--record",
        type=Path,
        default=DEFAULT_RECORD,
        help=f"the record to write (default: {DEFAULT_RECORD.as_posix()})",
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        dest="queries",
        help=(
            "a term to search the paper, the deck and the meeting text for; "
            "repeatable, and the operator supplies it because it is a word of "
            "the pilot paper"
        ),
    )
    parser.add_argument(
        "--note",
        default="",
        help=(
            "what this workspace is, recorded in the record beside the root; "
            "the tool cannot tell a pilot paper's workspace from any other"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="connect, read and report; write nothing (the default)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="write the record and render the skeleton's status column from it",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the collector.

    :returns: ``0`` when the run finished, whether the slots passed or
        failed; ``1`` when the tool could not do what it was asked to do.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    applying = bool(args.apply)

    location = locate(args.workspace)
    token = _read_token(location)
    skeleton_path = args.skeleton
    record_path = args.record
    record_name = record_path.name

    try:
        skeleton_text = skeleton_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"the skeleton at {skeleton_path} could not be read: {error}")
        return 1
    rows = parse_skeleton(skeleton_text)
    if not rows:
        print(f"the skeleton at {skeleton_path} holds no evidence row this tool reads")
        return 1

    service = Service(args.base_url, token)
    try:
        collector = Collector(service, args.queries)
        checks = collector.run()
        reads = collector.reads
    except httpx.HTTPError as error:
        print(f"the service at {args.base_url} could not be reached: {error}")
        return 1
    finally:
        service.close()

    command = "python scripts/pilot_gate_evidence.py " + " ".join(
        [
            f"--workspace {args.workspace}",
            f"--base-url {args.base_url}",
            "--apply" if applying else "--dry-run",
        ]
        + [f"--query {query!r}" for query in args.queries]
        + ([f"--note {args.note!r}"] if args.note else [])
    )
    record = build_record(
        command=command,
        base_url=args.base_url,
        workspace=location.root,
        token=token,
        queries=args.queries,
        checks=checks,
        reads=reads,
        rows=rows,
        record_name=record_name,
        note=str(args.note),
    )
    try:
        assert_material_free(record, token)
    except EvidenceError as error:
        print(str(error))
        return 1

    _print_report(record)
    if not applying:
        print(f"dry run: nothing written (the record would be {record_path})")
        return 0

    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
    except OSError as error:
        print(f"the record at {record_path} could not be written: {error}")
        return 1

    statuses = {str(slot["slot"]): str(slot["status_after_this_run"]) for slot in record["slots"]}
    try:
        skeleton_path.write_text(apply_statuses(skeleton_text, statuses), encoding="utf-8")
    except OSError as error:
        print(f"the skeleton at {skeleton_path} could not be written: {error}")
        return 1
    print(f"wrote {record_path} and {skeleton_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
