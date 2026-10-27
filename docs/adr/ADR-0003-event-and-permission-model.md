# ADR-0003: Event model and permission model

**Status:** Proposed
**Work order:** LC-P1-04 (workspace/tool permission boundary), LC-P1-05 (SQLite task store and transactional events), LC-P1-06 (checkpoint, operation reconciliation and revision)
**Date:** 2026-10-15

## Context and concrete problem

LabCairn's differentiating claim is that a research process is **traceable**. That claim is only worth anything if the record of what happened is durable, ordered, and honest about its own gaps. `docs/ARCHITECTURE.md` fixes the identity model — `Task` (continuing objective), `Run` (one execution attempt), `Stage` (bounded work unit), `Operation` (one side-effect attempt), `Approval`, `Checkpoint` — and states two invariants that drive this entire ADR:

> Application-owned SQLite is the canonical task authority. Event and state update commit together.
> Checkpoints are immutable versioned records; restart performs reconciliation before continuing a new Run on the same Task. Crash recovery must not imply resuming a model at an exact interrupted token.

LC-P1-05 turns the first into an engineering requirement: a **unique event sequence** and **transactionally coupled event/state transitions**. LC-P1-06 turns the second into three specific crash tests:

| # | Crash point | Requirement |
|---|---|---|
| 1 | before the side effect is written | no blind replay |
| 2 | after the write, before commit | no blind replay; the effect must be marked **uncertain**; reconcile before any replay |
| 3 | after commit, before the UI received the notification | no blind replay |

LC-P1-04 fixes the permission model: explicit allowed roots, read-only source material, separate task output, path normalization and symlink/junction guards, **resource-scoped `allow / ask / deny` with deny winning**, and approvals **bound to a canonical arguments digest and a task id**. LC-P1-04 also fixes the anti-injection invariant from `ARCHITECTURE.md`: *imported text never grants permissions*.

The concrete problem is that these three work orders describe a system that must be **honest about uncertainty**, and the two most obvious reference implementations are not. Neither upstream has a state for "I performed a side effect and I do not know whether it landed." Both resolve the ambiguity by *asserting* one answer. An earlier ADR can pick better primitives; this ADR has to define the contract itself, because the value of LabCairn depends on the record being right rather than merely plausible.

## Alternatives, including simpler/no-dependency option

### A1. Adopt OpenHands SDK's file-per-event `EventLog` as the durable record (REJECTED)

OpenHands' `EventLog` (`openhands-sdk/openhands/sdk/conversation/event_store.py :: EventLog`) is a genuinely careful piece of engineering: immutable frozen events, a monotonic integer index, a file lock, a length sidecar marker whose update is deliberately ordered *delete-then-write* so an interrupted marker update leaves no marker rather than a stale one, and an explicit documented statement that a missing marker is not proof of divergence so callers must fall back to an exact count. That reasoning is good and worth remembering.

It is still the wrong record for LabCairn, for four concrete reasons observed in the source:

1. **Ordering is derived from a directory scan, not from a transactional counter.** The sequence is the file index (`self._length`, `event_store.py:229`), recomputed by `_scan_and_build_index` (`event_store.py:320`). Nothing makes it contiguous by construction.
2. **A gap truncates the entire conversation.** `tests/sdk/conversation/test_event_store.py :: test_event_log_index_gaps_detection` constructs a log missing `event-00001` and asserts `len(log) == 0` — *all three* events are dropped, with the comment *"This is the current behavior, though it could be improved."* A one-event hole silently discards the entire history. LabCairn must be able to prove contiguity, and a SQLite `seq` with a `UNIQUE` index inside a transaction cannot have a gap: a rolled-back transaction consumes no sequence number, because the maximum is read from committed rows inside the same transaction.
3. **Events and state are two different files written by two different I/O operations with no shared transaction.** `EventLog.append` writes `events/event-NNNNN-<uuid>.json`; `ConversationState._save_base_state` (`conversation/state.py:430`) writes `base_state.json`. The batching in `ConversationState.__setattr__` and the `with state:` context manager (`state.py:743`) reduce write *count* and give thread-safety via a FIFO lock — the comment in `local_conversation.py:433` says so explicitly ("This callback runs while holding the conversation state's lock ... so updating state here is thread-safe"). **Thread-safe is not crash-atomic.** A crash between the two writes leaves them permanently inconsistent, and OpenHands has no reconciliation for the *state file*.
4. **The write guard is a lease, not a transaction.** `ConversationState.set_write_guard` forwards to `EventLog.set_write_guard`, and the concrete implementation (`openhands-agent-server/openhands/agent_server/event_service.py:469`) returns `self._lease.guarded_write(self._lease_generation)` from `ConversationLease` (`agent_server/conversation_lease.py:196`). That is a **fencing token** — it raises `ConversationOwnershipLostError` if a stale writer's generation is stale — which correctly solves *stale-writer fencing*. It solves nothing about atomicity.

**Verdict:** adopt the *ideas* (immutable frozen events, append-only, explicit sequence, delete-before-write marker discipline), reject the *mechanism* (files + directory scan + separate state file).

### A2. Adopt OpenHands' "orphan action → synthesize `AgentErrorEvent`" crash recovery (REJECTED — directly contrary to LC-P1-06)

This is the single most important negative finding in this study, and it is load-bearing for the decision.

On restart, `agent_server/event_service.py:1328-1371` does this: any conversation loaded with status `RUNNING` is stale; it flips to `ERROR`; it calls `ConversationState.get_unmatched_actions`; and for the first unmatched action it emits an `AgentErrorEvent` reading:

> `"A restart occurred while this tool was in progress. This may indicate a fatal memory error or system crash. The tool execution was interrupted and did not complete."`

**That sentence is an assertion, not a finding.** Nothing in the recovery path consulted the filesystem, the sandbox, or any receipt. The action may well have written a file, and the record now says it did not. The documented rationale (`local_conversation.py:2708-2712`) is that *"LLM providers reject conversation histories with orphaned tool-call requests, so we backfill them with a synthetic error"* — the motivation is **API conformance, not safety**.

The matching test makes the intent explicit. `tests/sdk/conversation/test_get_unmatched_actions.py :: test_crash_recovery_scenario_prevents_duplicate_execution` asserts the action is *not* returned as unmatched, with the message:

> `"Action with AgentErrorEvent should not be returned as unmatched, otherwise it will be re-executed causing duplicate observations"`

The fix for "the action might be re-executed" is therefore to **write a record that marks it handled**, not to determine whether it ran. That is exactly the blind replay LC-P1-06 forbids, performed by bookkeeping rather than by replay.

There is a second, related gap. `get_unmatched_actions` (`conversation/state.py:676`) matches `ObservationEvent`/`UserRejectObservation` by `action_id` but `AgentErrorEvent` by `tool_call_id`, "because it doesn't have an action_id field. This is important for crash recovery scenarios where an error event is emitted after a server restart." The consequence is documented as a bug in their own suite: `tests/agent_server/test_event_service.py :: test_start_skips_error_event_when_observation_already_exists` is subtitled *"Reproduces the gap get_unmatched_actions misses: an ObservationEvent that matches by tool_call_id but not by action_id ... without this guard we'd emit a duplicate observation-like event."* And `tests/integration/tests/a05_duplicate_tool_call_id.py:25` records the inverse failure, *"get_unmatched_actions() incorrectly identifies action as unmatched."*

So the reconciliation primitive is known-unsound in both directions, and LC-P1-06 case 2 is exactly the case it cannot express.

**Credit where due:** OpenHands does observe the *write/HEAD* half of the problem. `event_service.py:1335-1339` notes that crash recovery "scans the full log, not the active branch: the process may have died between writing an event file and persisting the advanced HEAD, so the leaf can lag the on-disk events." That is LC-P1-06 case 2, correctly identified — and then resolved by assuming the action did not complete.

### A3. Adopt OpenHands' confirmation policy as the permission model (REJECTED)

`openhands-sdk/openhands/sdk/security/confirmation_policy.py` defines `ConfirmationPolicyBase.should_confirm(risk: SecurityRisk) -> bool` with three implementations: `AlwaysConfirm`, `NeverConfirm`, and `ConfirmRisky(threshold=HIGH, confirm_unknown=True)`. `SecurityRisk` (`security/risk.py`) is a four-level enum — `UNKNOWN`, `LOW`, `MEDIUM`, `HIGH`. This is a well-built risk label and a poor permission model, for six reasons:

1. **No `deny`.** The vocabulary is `{confirm, don't confirm}`. There is no third state meaning "refuse, permanently". LC-P1-04 requires `allow / ask / deny`.
2. **Default is `NeverConfirm`.** `conversation/state.py:123` — `confirmation_policy: ConfirmationPolicyBase = NeverConfirm()`. Also default in `conversation/request.py:146` and `settings/model.py :: ConversationSettings._build_confirmation_policy`. An unknown tool runs.
3. **No resource identity.** Risk is a property of the *action*, not of the *resource being touched*. Nothing here can express "source materials are read-only".
4. **No arguments, no digest, no task scope, no expiry.** The policy is a pure function of one enum. An approval therefore cannot be bound to what was approved — LC-P1-04's central requirement is inexpressible.
5. **Approval is implicit and undocumented as an object.** There is no `confirm_pending_actions`. Accepting is *calling `run()` again*: `local_conversation.py` flips `WAITING_FOR_CONFIRMATION → RUNNING` and `agent/agent.py:716` picks up the unmatched actions — the comment reads `"Confirmation mode: Executing %d pending action(s)"` under the comment `# Check for pending actions (implicit confirmation)`. Nothing is persisted as "this approval was granted for these arguments".
6. **The security layer is one layer above the tool boundary.** The real invocation is `agent/agent.py :: Agent._execute_action_event:1499`, which at lines 1536/1538 does `observation = tool(action_event.action, conversation)`. Neither that method nor `_execute_actions` references `confirmation_policy`, `security_analyzer`, or `SecurityRisk`. The entire gate is one early return at `agent/response_dispatch.py:195` (`if self._requires_user_confirmation(...): return`, with `self._execute_actions(...)` at line 199). Any future or alternate caller of `_execute_actions` bypasses approval silently. Under LC-P1-04 the gate must be **below every caller**.

Two further observations, one damning and one reassuring:

- **`LLMSecurityAnalyzer` is self-attestation.** `security/llm_analyzer.py :: LLMSecurityAnalyzer.security_risk` is documented as *"Evaluate security risk based on LLM-provided assessment ... checks if the action has a security_risk attribute set by the LLM and returns it."* That field is populated by `agent/agent.py :: Agent._extract_security_risk:1204`, whose first line is `raw = arguments.pop("security_risk", None)` — it is popped out of **the tool-call arguments the requesting model itself just emitted**. The "LLM risk classifier" is the agent grading its own homework. It is inert when no analyzer is configured (`agent.py:1220` returns `UNKNOWN`), so this is a design landmine rather than a live default, but it is precisely the shape of failure LC-P1-04's "imported text never grants permissions" exists to prevent.
- **Upstream is alert to tool-call injection.** `security/toolshield_llm_analyzer.py` wraps user-controllable fields in XML with an *"UNTRUSTED CONTENT WARNING"*, and `tests/unit/security/test_toolshield_llm_analyzer.py` includes `TestParseRisk.test_only_smuggled_label_returns_unknown`, `test_inline_label_in_explanation_is_ignored`, `test_closing_tag_injection_in_arguments_neutralized`. LabCairn's anti-injection invariant is therefore not eccentric; it is standard. LabCairn's contribution is to enforce it **structurally** (see the contract below) rather than by prompt.

Also observed: `SecurityAnalyzerBase.should_require_confirmation` (`security/analyzer.py:71`) has **zero** call sites repo-wide — dead code. Analyzer *exceptions* do fail closed to `HIGH` (`analyzer.py:137-142`), which is good.

### A4. Adopt OpenHands' confirmation-lease / fencing-token scheme wholesale (PARTIALLY ADOPTED)

`ConversationLease` (`agent_server/conversation_lease.py`) is a well-designed fencing token: monotonic `generation`, `guarded_write(generation)` holds a `FileLock` and re-verifies ownership immediately before the write, and crash recovery is enabled by recording `owner_host`/`owner_pid` so a new process can detect a *dead* owner (`_owner_is_dead`, `_is_pid_alive`) and take over immediately instead of waiting the 45-second TTL. `_is_pid_alive` is deliberately conservative — on `PermissionError` or unknown `OSError` it reports the process as alive so "we never steal a lease that might still be in use."

LabCairn is a local single-user Phase 1 application (LC-P1-05), so the full lease machinery is unjustified. But the *failure* it addresses is real for us: a Web UI process and a CLI process can both be live on the same task. **Adopted:** a single integer `writer_epoch` on the task, bumped on every run start, and checked inside the same transaction that appends events. **Rejected:** the file lock, the TTL, the host/pid liveness probing.

### A5. Adopt deepagents' `FilesystemPermission` model (PARTIALLY ADOPTED — the strongest idea in either upstream)

This corrects an assumption worth stating plainly — but only part-way, and the part that is being corrected matters more than the part that stands. deepagents **does** have a real filesystem permission layer, and it is good. `deepagents/middleware/filesystem.py :: FilesystemPermission` is a dataclass of `(operations: list[FilesystemOperation], paths: list[str], mode: Literal["allow","deny","interrupt"])` with `FilesystemOperation = Literal["read", "write"]` (`filesystem.py:168`). `deepagents/middleware/permissions.py` is only a backward-compat re-export, so this is the single permission model in the library.

**Corrected scope (re-verified against source, 2026-10-15): this permission layer covers exactly seven built-in filesystem tools and nothing else.** The entire enforcement surface is enumerated in `middleware/_fs_interrupt.py:39-47 _FS_TOOL_PATH_ARGS`, which maps `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep` to an operation/path-argument/scope triple — and `_build_interrupt_on_from_permissions` (`:174-203`) iterates over precisely that dict when synthesizing HITL configs. There is no generic capability gate: `FilesystemPermission.operations` is typed `list[FilesystemOperation]` where `FilesystemOperation` is `Literal["read","write"]` — it cannot even express "execute", let alone name an arbitrary caller-supplied tool. deepagents' own `libs/ARCHITECTURE.md:85` concedes the adjacent point: *"Filesystem permissions enforce path-level policy on built-in filesystem tools. Permissions are not a visibility mechanism: a model may still see a tool whose call can later be denied or interrupted."*

So the corrected statement is: **deepagents has a genuine permission layer, but it is a filesystem-path policy engine, not a general tool-authorization capability gate.** A caller who passes their own `tools=[...]` to `create_deep_agent` receives no permission enforcement on those tools at all. This is precisely why LabCairn cannot copy the model: LC-P1-04 requires an `allow` / `ask` / `deny` verdict over *every* capability, keyed by capability identity, and deepagents' rule key is `(operation, glob pattern)` scoped to seven hardcoded tool names. The one generic approval path that does exist — the `interrupt_on: dict[str, bool | InterruptOnConfig]` parameter (`graph.py:288`) — is not deepagents' own machinery; it is a passthrough to LangChain's `HumanInTheLoopMiddleware` (`graph.py:400`) keyed by arbitrary tool name, merged with the generated filesystem entries so that caller entries win (`_merge_fs_interrupt_on:186-201`). It carries none of the durability LabCairn's `Approval` row requires.

What to adopt:

- **Deny is checked on both the declared path and the symlink-resolved target.** `_resolve_real_path` (`:421`) plus `_is_denied` (`:489`) means a symlink pointing into a denied tree is caught. LabCairn needs this and it is easy to get wrong.
- **Read results are filtered, not just blocked.** `_apply_permissions_to_ls_results` / `_apply_permissions_to_glob_results` (`:860`, `:871`) remove denied entries from listings, so the model never learns the denied name existed.
- **Recursive delete refuses to trust rule order.** `_find_delete_deny_patterns` (`:635`) states: when `has_descendants` is true a deny-write pattern blocks "regardless of rule order — an earlier allow rule can't guarantee every descendant is safe, since a later, more specific deny could still apply to one of them." That is deny-wins reasoning, arrived at independently, for the one operation where it was unavoidable.
- **Delete-by-ancestor is denied** (`test_recursive_delete_refused_when_descendant_denied`, `test_delete_refused_when_ancestor_denied`).
- **Rule patterns are validated at construction.** `__post_init__` (`:393`) rejects paths without a leading `/`, containing `..`, or containing `~`.
- **Permissions fail closed against unsupported backends.** `filesystem.py:1976-1980` raises rather than silently dropping rules when the backend provides command execution: *"Tool-level permissions for the execute tool are not implemented. Either remove permissions or use ..."*
- **An edited approval re-enters the deny check.** `_fs_interrupt.py:189-192`: the decision set is `approve / edit / reject / respond`, and *"`edit`ed calls still re-enter the tool and hit its pre-execution deny check"*. Approving an edited call cannot smuggle it past a deny.

What to reject:

- **Default is `allow`.** `_check_fs_permission` (`:408`) returns `"allow"` when no rule matches, and `test_default_effect_is_allow` asserts it. LC-P1-04 requires deny-wins with an implied default of deny.
- **First-match-wins, not deny-wins.** `_check_fs_permission` returns on the first matching rule, and `filesystem.py:654` documents it: *"the first rule (in declaration order) that matches wins."* `tests/unit_tests/test_permissions.py :: TestFindDeleteDenyPatternsExactFile.test_earlier_allow_wins_over_later_catch_all_deny` **asserts this behaviour as intended**, and `TestCheckFsPermissionInterrupt.test_deny_rule_takes_precedence_when_listed_first` shows deny only wins by being listed first. This is the exact opposite of LC-P1-04's "deny wins".
- **Path granularity only.** The rule key is `(operation, glob pattern)`. Nothing binds an approval to argument *content*, so an approved `write /outbox/report.md` also authorises overwriting it with different bytes.
- **`interrupt` is not an approval object.** It builds a LangGraph `InterruptOnConfig` (`_fs_interrupt.py:174`) delegating to `HumanInTheLoopMiddleware` and a checkpointer. Nothing is persisted as a scoped, expiring, digest-bound grant.
- **A known deny bypass, documented by upstream.** `backends/protocol.py:646-647`: *"`FileInfo.path` is always absolute. `_check_fs_permission` matches `deny` rules against absolute patterns only, so a backend returning a relative path silently bypasses every deny rule."* LabCairn must make relative returns impossible rather than documenting the hazard.
- **Unanchored patterns over-fire.** `filesystem.py:388-390` notes `/**/secrets` collapses to `/` and "conservatively over-fires for any bulk call." Fail-safe, but imprecise. The mechanism is at `_fs_interrupt.py:26-31` (`"bulk"` scope) and `:129-143`: a pathless or `.`-normalised bulk call "refers to the whole accessible tree just like a missing path arg, so collapse to `/`" — added specifically so `path="."` cannot bypass a rule. Rejected as a policy primitive because an operator cannot reason about blast radius, but the *intent* (never let a shorthand resolve to the whole tree) is adopted.
- **The upstream philosophy is the opposite of LC-P1-04's, and it is stated deliberately.** `README.md:91`: *"Deep Agents follows a "trust the LLM" model. The agent can do anything its tools allow. Enforce boundaries at the tool/sandbox level, not by expecting the model to self-police."* Read together with the default-`allow` return (`filesystem.py:418`) and first-match-wins (`:654`), this is a coherent position: put the hard boundary in the sandbox, keep the policy layer advisory. LabCairn takes the opposite position — LC-P1-04 mandates **deny-wins** with **default-deny** (`C5`), because a local research workbench must remain auditable *before* a sandbox is ever involved. The quoted sentence is recorded here as the design intent we are declining, so the divergence is deliberate rather than accidental.

### A6. Adopt deepagents' planning / subagent model as the Stage mechanism (REJECTED)

Three findings, all negative, all relevant.

**There is no core planning state, and the project removed it deliberately.** The `write_todos` tool does not originate in deepagents — it comes from LangChain's `TodoListMiddleware`, and in this repository it appears only in opt-in harness profiles (`deepagents/profiles/harness/_openai_codex.py:19,77`, `profiles/harness/_nvidia_nemotron_3_ultra.py:379`). The removal is on the record as a breaking change, `libs/deepagents/CHANGELOG.md:221`: *"`create_deep_agent` no longer includes `TodoListMiddleware` by default, the `write_todos` tool, `todos` state channel, and todo-planning prompt are now absent. Pass `middleware=[TodoListMiddleware()]` to restore them on the main agent; add it to each `SubAgent`'s middleware to restore them there."* The removing commit is `9340518 feat(sdk,code,quickjs)!: make the ToDoListMiddleware list opt-in (#4929)`. The plan is therefore (a) optional, (b) third-party, (c) produced by the model calling a tool, and (d) materialised as conversation content. LC-P1-07 already states the consequence — *"A plan is a task artifact, not a new authoritative store"* — and the upstream evidence supports that rule rather than arguing against it. See also "Documentation claims vs. shipped code" under Upstream evidence below: the module docstring of `graph.py` still advertises planning at version 0.7.25, twenty-five releases after the removal landed in 0.7.0.

**The subagent boundary is contextual, not capability-scoped.** `deepagents/middleware/subagents.py :: TaskToolSchema` (`:455`) takes exactly `description` and `subagent_type`, dispatched through a `task` tool. `TASK_TOOL_DESCRIPTION` (`:500`) states: *"Each invocation is stateless by default: the agent sees only the prompt you give it and returns a single final report."* There is a "forked" mode (`_fork_messages`, `_is_forked_subagent`) that inherits the parent's messages, but that is a context choice, not a permission boundary. `TaskToolSchema` does carry a nice schema guard (`_reject_unknown_keys`, `:467`) whose docstring explains the real failure it prevents — models putting the real instructions under an invented `prompt` key and silently dispatching with a short label — but that is argument validation, not authority control.

**Persistence is explicitly ephemeral, and there is no state/history separation.** `deepagents/backends/state.py :: StateBackend` is documented as *"Store files in LangGraph agent state (ephemeral). Files persist within a conversation thread but not across threads."* It routes reads and writes through LangGraph's `CONFIG_KEY_READ`/`CONFIG_KEY_SEND` as channel writes to a `files` state key. Separately, `create_deep_agent` ships **no checkpointer of its own**: the parameter defaults to `None` (`graph.py:292`) and is forwarded verbatim (`:1000`), so crash recovery depends entirely on a caller-supplied LangGraph checkpointer. And the state schema is a *single merged document* — `DeepAgentState(AgentState)` (`graph.py:74-77`) carries `messages` (with a `DeltaChannel` reducer for checkpoint-size reasons only), while each middleware contributes its own fields to that same schema, which is what the checkpointer serializes. There is no separate store for business state versus conversation history, and therefore no transaction that can commit both or either.

**This is the decisive rejection reason for LC-P1-06.** LC-P1-06 requires checkpoint and recovery behaviour on LabCairn's terms: operations and business state commit together in one SQLite transaction, checkpoints are immutable versioned records, recovery *enters* an explicit `UNCERTAIN` state rather than silently resuming, and business state is separable from conversation history. deepagents provides none of these — it delegates durability to an external framework, and it co-mingles the two concerns LC-P1-06 needs kept apart. Adopting it would mean inheriting the coupling without inheriting the guarantees.

**Subagents share the parent's filesystem backend; there is no per-subagent isolation.** `graph.py:903` passes the parent agent's `backend` straight into `SubAgentMiddleware(backend=backend, ...)`, which stores it as `self._backend` (`middleware/subagents.py:974-980`). A delegated subagent is therefore not confined to a subdirectory or a separate store; it operates on the same namespace as its parent. `SubAgent.mode` defaults to `"isolated"` — the docstring (`subagents.py:86-88`) is explicit: *"By default the subagent is isolated: it receives only the delegated task description"* — and `mode="fork"` inherits the parent's conversation, but is marked `!!! warning "Experimental"` (`subagents.py:91-93`). Confinement is delegated entirely to `SubAgent.permissions`, and that is wholesale rather than additive (`subagents.py:162-166`): *"If omitted, inherits the parent agent's permissions. If specified, replaces the parent's permissions entirely for this subagent."* LabCairn's `C5` composes allow/ask/deny across capabilities and has no such replace-parent wholesale switch, because a subtask that silently loses the parent's deny rules is a privilege-escalation path.

**Verdict:** adopt nothing structural. Keep the schema-strictness lesson (A6's `_reject_unknown_keys`): closed argument schemas, rejection of unknown keys, and errors returned to the model naming the offending key.

### A7. No-dependency option: append-only JSONL event log plus periodic JSON snapshot (REJECTED as the primary store)

The simplest thing that could work: append newline-delimited JSON events to one file, rewrite a state snapshot occasionally, no database. It is genuinely simpler and it is what A1 is, minus the per-event files.

It is rejected because it cannot deliver the one property LC-P1-05 calls non-negotiable. A JSONL append and a state snapshot are two writes with no shared commit point, so event/state coupling is unavailable by construction. It also cannot enforce a unique gapless sequence without adding exactly the bookkeeping that SQLite's transaction already provides. And the reconciliation probes LC-P1-06 requires need indexed queries — *"which operations for this task are in a non-terminal state"*, *"which approvals reference source hash H"* — which turn every recovery into a full-file scan whose cost grows with history.

**Partially retained:** content hashes and receipt documents remain plain versioned JSON files on disk. They are data, not the transaction log.

## Upstream evidence (reference only)

### Reference A — OpenHands SDK

- **Repository URL:** https://github.com/OpenHands/software-agent-sdk.git (origin confirmed via `git remote get-url origin`)
- **Exact commit SHA:** `8efff8d3cf1a5a3fcf7ce5e3b97c7f00684d9547` — **verified during this study** with `git -C E:/labcairn-upstreams/openhands-sdk rev-parse HEAD`; matches the pin given in the task. `git log --oneline -1` → `8efff8d fix(agent-server): apply enable_browser to /server_info usable_tools (#5924)`.
- **License at this revision:** MIT (`LICENSE` line 1: `MIT License`, `Copyright (c) 2026 OpenHands contributors`).

**Inspected paths:**

- `openhands-sdk/openhands/sdk/event/base.py` — `Event`, `LLMConvertibleEvent`
- `openhands-sdk/openhands/sdk/event/types.py` — `EventType`, `SourceType`, `ROOT_PARENT_ID`
- `openhands-sdk/openhands/sdk/event/__init__.py` — full event export list
- `openhands-sdk/openhands/sdk/event/security.py` — `SecurityAnalysisEvent`
- `openhands-sdk/openhands/sdk/event/user_action.py` — `PauseEvent`, `InterruptEvent`
- `openhands-sdk/openhands/sdk/event/resume_transcript.py` — `RESUME_CONTEXT_MARKER`, `render_resume_transcript`
- `openhands-sdk/openhands/sdk/event/error_classification.py` — `FailureKind`, `ErrorClassification`, `classify_error`
- `openhands-sdk/openhands/sdk/event/llm_convertible/observation.py` — `ObservationBaseEvent`, `ObservationEvent`, `UserRejectObservation`, `AgentErrorEvent`
- `openhands-sdk/openhands/sdk/conversation/event_store.py` — `EventLog`
- `openhands-sdk/openhands/sdk/conversation/persistence_const.py` — `BASE_STATE`, `EVENTS_DIR`, `EVENT_FILE_PATTERN`
- `openhands-sdk/openhands/sdk/conversation/events_list_base.py` — `EventsListBase`
- `openhands-sdk/openhands/sdk/conversation/state.py` — `ConversationState`, `ConversationExecutionStatus`, `get_unmatched_actions`, `_save_base_state`, `__setattr__`
- `openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py` — `_default_callback`, `_emit_orphaned_action_errors`, `reject_pending_actions`, `rerun_actions`
- `openhands-sdk/openhands/sdk/security/confirmation_policy.py`, `security/risk.py`, `security/llm_analyzer.py`, `security/analyzer.py`
- `openhands-sdk/openhands/sdk/agent/agent.py` — `_extract_security_risk:1204`, `_execute_action_event:1499`, `_step:707`
- `openhands-sdk/openhands/sdk/agent/response_dispatch.py:185-199` — the confirmation early-return
- `openhands-sdk/openhands/sdk/context/view/properties/batch_atomicity.py` — `BatchAtomicityProperty`
- `openhands-sdk/openhands/sdk/utils/files.py` — `atomic_write_text`
- `openhands-agent-server/openhands/agent_server/event_service.py` — `_write_guard:469`, restart recovery `1328-1371`
- `openhands-agent-server/openhands/agent_server/conversation_lease.py` — `ConversationLease`, `guarded_write`, `_owner_is_dead`

**Inspected tests:** `test_event_log_index_gaps_detection`, `test_get_single_item_recovers_from_stale_index`, `test_append_syncs_when_marker_is_missing`, `test_event_log_concurrent_writes_serialized`, `test_event_log_cold_reload_past_100k_events` (all `tests/sdk/conversation/test_event_store.py`); `test_crash_recovery_scenario_prevents_duplicate_execution`, `test_agent_error_event_matching_by_tool_call_id`, `test_non_executable_action_is_not_considered_unmatched` (`tests/sdk/conversation/test_get_unmatched_actions.py`); `test_start_skips_error_event_when_observation_already_exists` (`tests/agent_server/test_event_service.py:2426`); `test_event_loss_race_condition_with_ws_delay` (`tests/cross/test_event_loss_repro.py`); `TestConfirmationMode.*` (`tests/sdk/conversation/local/test_confirmation_mode.py`); `TestParseRisk.test_only_smuggled_label_returns_unknown` and siblings (`tests/sdk/security/test_toolshield_llm_analyzer.py`).

**What was actually observed (stated as behaviour, not inference):**

- An event is an immutable, frozen, `extra="forbid"` Pydantic model carrying `id` (UUID), `timestamp` (ISO string), `source`, and `parent_id`. Events form a **tree**, not only a log: `parent_id` plus the `ROOT_PARENT_ID = "__root__"` sentinel, with `EventLog.path_to_root` walking the active branch. A validator rejects any event whose own `id` equals the sentinel, so a `parent_id == ROOT_PARENT_ID` unambiguously means root.
- There is **no `Event.seq` field**. Ordering is the file index. `EventLog.append` returns that index, but it is `self._length`, recomputed from a directory listing.
- Action/observation pairing is by **explicit foreign key**, not adjacency: `ObservationEvent.action_id` → `ActionEvent.id`, and `ObservationBaseEvent.tool_call_id` on both sides. `AgentErrorEvent` has no `action_id` and is matched by `tool_call_id` only.
- `Event` config is `frozen=True, extra="forbid"`; events are never mutated after append.
- `atomic_write_text` (`utils/files.py:21`) gives **per-file** atomicity: `mkstemp` → `fchmod` → write → `flush` → `fsync` → `os.replace`. There is no multi-file atomicity.
- `EventLog`'s class docstring warns that `flock()` "does NOT work reliably on NFS mounts or network filesystems."
- A gap in the event index stops the scan entirely (`test_event_log_index_gaps_detection` asserts `len(log) == 0`).
- `ErrorClassification` is an explicitly privacy-safe closed vocabulary — `kind / retryable / user_action / error_id` — whose docstring states `detail` "is inspected locally only to map broad third-party errors to this closed vocabulary; it is never copied here or sent to telemetry."
- `SecurityAnalysisEvent` "is not sent to the LLM" and is emitted "even when the policy (for example `NeverConfirm`) never consults it" — i.e. the verdict is recorded for the operator while being withheld from the model.
- `read_only_tool` exists only as a parameter of `_extract_security_risk` whose sole effect is to return `UNKNOWN` (`agent.py:1214`). Under the default `NeverConfirm`, `UNKNOWN` means *proceed*. **There is no read-only enforcement anywhere in the SDK**; the only other `read_only` hit in the tree is `read_only_hint` in `mcp/tool.py:61`, an MCP protocol field passed through to clients.
- `ConversationExecutionStatus` includes `WAITING_FOR_CONFIRMATION`, and `is_terminal()` deliberately excludes `IDLE` "to avoid false positives when the WebSocket delivers the initial state update during connection."

**Explicitly inferred, not observed:** that no alternate caller of `_execute_actions` exists outside `Agent._step`. The non-test call sites found were read; a full control-flow enumeration was not performed. Also inferred: the `LocalWorkspace` docstring ("suitable for development and testing scenarios where the agent should operate directly on the host system") combined with the absence of any explicit "not a security boundary" disclaimer across the whole tree implies the local workspace is not treated as a hardened boundary. Searches for `not a security boundary|is not a sandbox|provides no isolation|security boundary|does not isolate` returned zero matches, including in Markdown — **the absence of a disclaimer is itself the finding.** The nearest signal is `openhands-workspace/openhands/workspace/agent_sandbox/deploy/sandboxtemplate.yaml:46`, a commented-out `# runtimeClassName: gvisor   # uncomment for strong isolation of untrusted code`, implying the shipped default is not strong isolation.

**License obligations:** MIT. **No OpenHands source code is copied or adapted into LabCairn by this ADR.** The observations above are behavioural notes with file and symbol citations; the only upstream text reproduced is short quoted error strings, docstring sentences and code comments used as evidence, each attributed to its path and symbol. If any future change adapts `atomic_write_text` or the lease design, a per-file license/notice review is required before the code lands.

### Reference B — deepagents

- **Repository URL:** https://github.com/langchain-ai/deepagents.git (origin confirmed via `git remote get-url origin`)
- **Exact commit SHA:** `825acb3ca03bd103e4df6013b122eca8475d1982` — **verified during this study** with `git -C E:/labcairn-upstreams/deepagents rev-parse HEAD`; matches the pin given in the task. `git log --oneline -1` → `825acb3 feat(sdk): report async subagents that are waiting for a human (#6842)`.
- **Package version at this revision:** `deepagents` 0.7.25 (`libs/deepagents/pyproject.toml:3`).

**Inspected paths:**

- `libs/deepagents/deepagents/middleware/filesystem.py` — `FilesystemPermission:366`, `_check_fs_permission:408`, `_resolve_real_path:421`, `_permission_error:435`, `_resolved_permission_error:447`, `_delete_permission_error:465`, `_is_denied:489`, `_find_delete_deny_patterns:635`, `FilesystemMiddleware.__init__:1903`, backend incompatibility guard `:1976`
- `libs/deepagents/deepagents/middleware/_fs_interrupt.py` — `_build_interrupt_on_from_permissions:174`, decision set `:189-194`
- `libs/deepagents/deepagents/middleware/permissions.py` — backward-compat re-export only
- `libs/deepagents/deepagents/middleware/subagents.py` — `SubAgent:84`, `CompiledSubAgent:230`, `TaskToolSchema:455`, `TASK_TOOL_DESCRIPTION:493`
- `libs/deepagents/deepagents/backends/protocol.py` — `BackendProtocol:404`, `PERMISSION_DENIED:60`, the relative-path bypass note `:646`
- `libs/deepagents/deepagents/backends/state.py` — `StateBackend:38`
- `libs/deepagents/deepagents/backends/filesystem.py`, `sandbox.py:1092,1106,2124`, `local_shell.py:57,76`
- `libs/deepagents/deepagents/profiles/harness/_openai_codex.py`, `_nvidia_nemotron_3_ultra.py`
- `libs/deepagents/deepagents/graph.py` — module docstring `:1-6`, `DeepAgentState:74`, `create_deep_agent` signature `:283-296`, default middleware stack `:893-919`, `checkpointer` default `:292` and forwarding `:1000`, hardcoded `recursion_limit` `:1008`, `_merge_fs_interrupt_on:186`
- `libs/deepagents/deepagents/middleware/_state.py` — `PrivateStateAttr` helpers `:13-49`
- `libs/deepagents/deepagents/middleware/rubric.py` — `RubricMiddleware.max_iterations = 3` (`:570`)
- `libs/ARCHITECTURE.md:69,81,85`; `libs/deepagents/README.md:51,71,112`; `libs/deepagents/CHANGELOG.md:221`

**Inspected tests:** `libs/deepagents/tests/unit_tests/test_permissions.py` (136 test functions), including `TestRecursiveDeletePermissions::test_recursive_delete_refused_when_descendant_denied`, `::test_delete_refused_when_ancestor_denied`, `TestFindDeleteDenyPatterns::test_mode_and_operation_filtering`, `TestFindDeleteDenyPatternsExactFile::test_earlier_allow_wins_over_later_catch_all_deny`, `::test_deny_still_blocks_when_it_matches_first`, `::test_interrupt_rule_is_not_a_denial`, `TestFilesystemPermission::test_default_effect_is_allow`, `::test_path_with_dotdot_raises`, `::test_path_with_tilde_raises_not_implemented`, `TestCheckFsPermissionInterrupt::test_deny_rule_takes_precedence_when_listed_first`, `TestBuildInterruptOnFromPermissions::test_registers_only_tools_whose_op_could_interrupt`. Also `libs/deepagents/tests/integration_tests/test_hitl.py :: test_hitl_agent`, `::test_subagent_with_hitl`, `::test_subagent_with_custom_interrupt_on`.

**What was actually observed:**

- The permission rule key is `(FilesystemOperation, glob pattern)` where `FilesystemOperation = Literal["read", "write"]` (`filesystem.py:168`). Mode is `allow` (default) / `deny` / `interrupt`.
- Rule resolution is **first-match-wins in declaration order**, explicitly documented at `filesystem.py:654` and asserted by a named test.
- No rule match returns `"allow"` (`filesystem.py:418`).
- **Recursive delete is the documented exception**: deny applies "regardless of rule order" when the target has descendants, because an earlier allow "can't guarantee every descendant is safe" (`filesystem.py:646-647`).
- Rules are applied at construction (`__post_init__:393` rejects non-absolute paths, `..`, and `~`), at read/write dispatch (`_permission_error:435`), at symlink resolution (`_resolved_permission_error:447`, `_is_denied:489`), at delete (`_delete_permission_error:465`), and to bulk-read results (`_apply_permissions_to_ls_results:860`, `_apply_permissions_to_glob_results:871`).
- `interrupt` produces LangGraph `InterruptOnConfig` entries with a `when` predicate matching the tool call's path argument, offered to the approver as `["approve", "edit", "reject", "respond"]` (`_fs_interrupt.py:189-194`).
- Permissions are **opt-in** (`_permissions: list[FilesystemPermission] | None = None`, `:1903`) and are **refused** when combined with a shell-capable backend, with an explicit error message rather than a silent downgrade (`:1976-1980`).
- `test_hitl.py`'s module docstring states the suite "assert[s] SDK structural state (interrupt payload shape, decision list contents, post-resume tool messages), **not model behavior quality**," and the HITL tests require `langchain_anthropic` (`pytestmark = pytest.mark.requires(...)`) — so they are not part of the default offline test run.
- `StateBackend` is documented as ephemeral and scoped to a conversation thread.
- `TASK_TOOL_DESCRIPTION` states subagent invocations are "stateless by default."
- No `write_todos` implementation exists in the deepagents package; the tool comes from LangChain's `TodoListMiddleware` and appears only in harness profiles.

**Scope of the permission layer (second verification pass, 2026-10-15).** The complete enforcement surface is the seven-tool map `_FS_TOOL_PATH_ARGS` (`_fs_interrupt.py:39-47`): `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`. `_build_interrupt_on_from_permissions` (`:174-203`) iterates exactly that dict, and `_check_fs_permission` is reached only from filesystem tool dispatch. `FilesystemOperation` is `Literal["read", "write"]` (`filesystem.py:168`) — two members, so the policy vocabulary cannot name an arbitrary tool or an "execute" class. **Caller-supplied tools passed via `tools=` receive no permission enforcement whatsoever.** The only non-filesystem approval path is the caller-supplied `interrupt_on` parameter (`graph.py:288`), which is a passthrough to LangChain's `HumanInTheLoopMiddleware`; `_merge_fs_interrupt_on:186-201` merges it over the generated filesystem entries with caller entries winning. Verified by reading the parameter, the merge function, and the HITL middleware docstring reference at `graph.py:400`.

**Design philosophy, quoted.** `README.md:91`: *"Deep Agents follows a "trust the LLM" model. The agent can do anything its tools allow. Enforce boundaries at the tool/sandbox level, not by expecting the model to self-police."* Consistent with the observed default-`allow` (`filesystem.py:418`) and first-match-wins (`:654`) behaviour. LabCairn adopts deny-wins with default-deny instead (see `C5`).

**Iteration limits.** The recursion limit is hardcoded at `graph.py:1008` — `.with_config({"recursion_limit": 9_999})` — applied by `create_deep_agent` itself and not exposed as a parameter. The only iteration cap anywhere in the core package is `RubricMiddleware.max_iterations: int = 3` (`rubric.py:570`), which bounds grader revisions only and has no bearing on agent loop length.

**Checkpointing.** `checkpointer: Checkpointer | None = None` (`graph.py:292`), forwarded verbatim to `create_agent` (`:1000`). deepagents bundles no checkpointer, so durability is entirely the caller's responsibility. `DeepAgentState(AgentState)` (`graph.py:74-77`) is one merged state document: `messages` uses a `DeltaChannel` reducer (a checkpoint-size optimisation, not a separation of concerns), and middleware state fields are merged into the same schema. Only fields explicitly annotated `PrivateStateAttr` are withheld from subagent forwarding (`middleware/_state.py:13-49`) — and even that is a *delegation* boundary, not a *persistence* boundary.

**Subagent filesystem confinement.** `graph.py:903` passes the parent `backend` into `SubAgentMiddleware`, which stores it (`subagents.py:974-980`). No separate namespace or directory. `SubAgent.mode` defaults to `"isolated"` (description-only context; `subagents.py:86-88`); `mode="fork"` inherits parent conversation and is flagged experimental (`:91-93`). `SubAgent.permissions` replaces the parent's rules wholesale rather than composing (`:162-166`).

**Not established by this study, stated as open.** (a) The `write_todos` schema and whether its todos live in graph state or in message text — that middleware is LangChain's, not present in this repository, so it cannot be settled from this tree. (b) `FilesystemOperation` membership is *not* open: it is exhaustively `Literal["read","write"]` (`filesystem.py:168`), so "execute"-class operations cannot be expressed. (c) No deepagents-owned approval mechanism for non-filesystem tools was found; the `interrupt_on` passthrough described above is LangChain's, and is the only such path observed.

**Explicitly inferred, not observed:** the absence of any *other* permission mechanism. The first pass established this by grepping the core package for `permission|approval|deny|allow|human_in_the_loop|interrupt_on|interrupt_before`, and by reading `middleware/permissions.py`, which is a one-line re-export module. The second pass converted part of that negative inference into a positive observation: `_FS_TOOL_PATH_ARGS` (`_fs_interrupt.py:39-47`) is an exhaustive enumeration of the tool names the filesystem permission layer can gate, and the `interrupt_on` passthrough (`graph.py:288`) is the only non-filesystem approval path found. What remains inferential is the *universal* claim — `libs/acp`, `libs/code`, `libs/partners` and the non-MIT benchmark adapters were not searched exhaustively, and a negative finding by grep is weaker evidence than a positive one.

**License obligations:** MIT (`libs/deepagents/LICENSE`, root `LICENSE`, and `pyproject.toml` `license = { text = "MIT" }`). **No deepagents source code is copied or adapted into LabCairn by this ADR**; the only upstream text reproduced is short quoted docstring sentences and comments used as evidence, each attributed to its path and symbol.

### Documentation claims vs. shipped code (a process correction)

This study surfaced a defect worth recording as a rule rather than as a footnote, because it invalidates a premise that had already been written into `docs/UPSTREAM_REFERENCES.md` and `docs/PHASE_1_WORKORDERS.md`.

**The finding.** deepagents documents a planning capability in four separate places, and none of it exists in the code:

- `libs/deepagents/deepagents/graph.py:3-6`, the module docstring of the file that *is* the entry point: `create_deep_agent`, "the main entry point for constructing a fully configured deep agent with **planning**, filesystem, subagent, and summarization middleware."
- `libs/ARCHITECTURE.md:69`: base scaffolding "creates the capabilities expected of a deep agent: **planning**, filesystem access, subagent delegation, summarization, and request cleanup."
- `libs/ARCHITECTURE.md:81`: built-in middleware contributes "the standard Deep Agents tools, including **todo management**, filesystem tools, and subagent delegation."
- `libs/deepagents/README.md:51`: "The agent **can plan**, read/write files, and manage its own context." And `README.md:71`: "Use **Deep Agents** when you want the full harness — **planning**, context management, delegation — out of the box."

What the code actually does, at the same commit:

- The default middleware stack assembled in `graph.py:893-919` is `FilesystemMiddleware` → optional `SubAgentMiddleware` → `create_summarization_middleware(...)` → `PatchToolCallsMiddleware()`. There is no planning or todo middleware anywhere in it.
- The `create_deep_agent` signature (`:283-296`) has no planning, todo, or plan parameter.
- `grep -rn "write_todos\|TodoListMiddleware" libs/deepagents/` finds the tool only in `profiles/harness/_openai_codex.py:19,77` (an opt-in provider profile) and in tests. The implementation is LangChain's.
- `libs/deepagents/CHANGELOG.md:221` records the removal as a **breaking change**: *"`create_deep_agent` no longer includes `TodoListMiddleware` by default, the `write_todos` tool, `todos` state channel, and todo-planning prompt are now absent."* The commit is `9340518 feat(sdk,code,quickjs)!: make the ToDoListMiddleware list opt-in (#4929)`.

**Why it stayed wrong.** The docstring, the README and the architecture overview were not updated after the breaking change. The removal landed in `0.7.0` (2026-07-29); the pinned snapshot is `0.7.25`, twenty-five releases later, and all four claims are still there — stale text describing a version of the library that no longer exists at this SHA. Anyone reading the project's own documentation — the cheapest possible source — would conclude the harness ships planning, and would be right about the wording and wrong about the software.

**The rule this establishes for all upstream study.** A README, a module docstring, an architecture overview, a changelog entry, and a paper are *claims*, not evidence. A capability is only established by a code path that constructs it: a middleware appended to the assembly list, a parameter in the public signature, a symbol defined in the repository rather than imported from a dependency. The cheapest check is to enumerate the default stack and diff it against what the prose promises. This has already changed two documents (`docs/UPSTREAM_REFERENCES.md` and the LC-P1-00 entry in `docs/PHASE_1_WORKORDERS.md`, both corrected) and it is the reason the permission scope in `A5` was narrowed on a second pass rather than taken from the first pass's summary.

**Caveat on the rule itself.** This cuts both ways: absence from the code is not proof of absence from the project's intent, and the removed feature is recoverable by passing `middleware=[TodoListMiddleware()]`. The conclusion drawn here is narrow and defensible — *planning is not part of the default deep agent harness at this commit, and must not be credited as a study finding for upstream capability* — not "deepagents cannot plan."

### Security note on the reference material

Both trees are untrusted third-party data. Neither was cloned, moved, modified, or executed; only read-only file access and read-only git commands were used. Two concrete hazards were found and **not** acted on:

- `openhands-sdk/.openhands/setup.sh` contains `curl -LsSf https://astral.sh/uv/install.sh | sh` followed by `make build`, and `.openhands/hooks.json` auto-registers `.openhands/hooks/on_stop.sh` as a `stop` hook with a 600-second timeout. Neither was run.
- `openhands-sdk/AGENTS.md` (38 KB) opens with `<ROLE>You are a collaborative software engineering partner for this repository...` followed by a "Working Agreement". It is a prompt-injection surface aimed at coding assistants and was treated as repository documentation, not as instruction. Counting `AGENTS.md` / `CLAUDE.md` / `SKILL.md` / `.mcp.json` / `hooks.json` / `setup.sh` across both trees gives **36 files in openhands-sdk and 44 in deepagents**; `deepagents/.mcp.json` would register two remote MCP servers against LangChain documentation endpoints if honoured.

## Decision and why this fits LabCairn

**Decision.** Adopt neither upstream as a base. Build an independent, application-owned SQLite record with a closed event vocabulary, a monotonic `seq` allocated inside the transaction, an explicit `UNCERTAIN` operation state that recovery *enters* rather than assumes away, and a first-class `Approval` row bound to a canonical-arguments digest and a task scope. Adopt four specific mechanisms, each cited above: immutable frozen events (OpenHands), delete-before-write sidecar discipline (OpenHands), symlink-resolved double-checking plus filtered read results (deepagents), and deny-wins for destructive operations generalised to *all* operations (deepagents' recursive-delete reasoning).

**What is explicitly not adopted from deepagents' permission layer.** Not the model — only its techniques. deepagents' `FilesystemPermission` cannot be used as-is because its enforcement surface is seven hardcoded built-in filesystem tools (`_FS_TOOL_PATH_ARGS`) and its default is `allow` with first-match-wins; a caller-supplied tool is simply not in scope. LabCairn needs a verdict over *every* capability, keyed by capability identity, defaulting to `DENY`, where any matching `deny` is final. That is a different model with the same name's trappings, and the divergence is deliberate: upstream's stated philosophy is *"trust the LLM ... Enforce boundaries at the tool/sandbox level"* (`README.md:91`), LabCairn's is deny-wins inside the application before any sandbox exists. The techniques survive the disagreement — symlink resolution, filtered read results, construction-time pattern validation, and the deny-wins reasoning itself — because techniques are independent of the default they run under.

**Why this fits.** LC-P1-06's three crash cases are the whole design driver, and the three map onto three properties:

- Case 1 (crash before write) is handled by a **write-ahead intent**: `operation_attempted` commits in its own transaction *before* the side effect is attempted. If that transaction never committed, nothing was attempted and replay is unconditionally safe.
- Case 2 (crash after write, before commit) is the case neither upstream can express. It is handled by the `UNCERTAIN` state plus a mandatory read-only reconciliation probe before any replay is permitted.
- Case 3 (crash after commit, before UI receipt) is handled by making `seq` client-resumable: the client sends `after_seq` and receives exactly the tail. Because the operation row and its event committed together, case 3 requires **no** reconciliation and **no** replay — the only thing missing is a notification, which is exactly what case 3 is.

**On the anti-injection invariant.** LC-P1-04 requires that imported text never grants permissions. Upstream handles this with prompt engineering (ToolShield's XML wrapping plus smuggling tests), which is necessary but not sufficient. LabCairn enforces it *structurally*: the policy evaluator's signature admits only application-supplied values, and the argument schema of every capability is a closed model. There is no parameter through which document content can reach a decision, so no amount of injected text can change a decision. This is a property of the type signature, testable by inspection, not a promise made in a system prompt.

## Risks, tradeoffs and reversibility

**R1 — SQLite becomes a correctness dependency.** Every durability property above rests on one engine. *Mitigation:* the transactional boundary is deliberately narrow (events plus state rows, nothing else), the schema is plain relational, and the recovery probes are independent of SQL. *Reversibility:* a SQLite-specific dependency is a Phase 1 local-only decision; the event contract is storage-agnostic by construction.

**R2 — `PRAGMA foreign_keys` is off by default in SQLite.** If it is not enabled per-connection, referential integrity is silently unenforced and the ledger can hold orphaned events. *Mitigation:* make it a startup assertion, not a convention — the application refuses to start if `PRAGMA foreign_keys` is not `1`, and a test asserts it. The same applies to `journal_mode=WAL` and the chosen `synchronous` level; durability claims must name the level actually configured.

**R3 — Reconciliation probes can be wrong.** A probe that concludes "absent" when the file exists causes a double write; one that concludes "present" when it does not loses the effect silently. *Mitigation:* the probe compares a **content hash**, never existence alone; a present-but-different result is `CONFLICT`, which is never auto-resolved; and `UNCERTAIN` operations block downstream progression until resolved. The probe is itself an Operation and goes through the same gate.

**R4 — Deny-wins is more surprising to operators than first-match-wins.** A `deny` rule anywhere in the policy shadows every `allow`. *Mitigation:* the CLI/API must return the *specific* matching deny rule in the refusal reason, so the operator can see which rule fired. deepagents' delete path already does this (`_delete_permission_error` cites the matched patterns) and the same affordance is adopted.

**R5 — Digest brittleness.** If canonicalisation changes between versions, an approval granted under v1 will not match under v2, and users will be asked again. *Mitigation:* the digest input includes `schema_version: 1` explicitly, so a change is a visible versioned break rather than a silent invalidation. Failing toward "ask again" is the safe direction.

**R6 — Write-ahead intent costs an extra transaction per side effect.** Roughly doubles the write path for operations. *Mitigation:* acceptable in Phase 1; the two transactions are the minimum that makes case 2 distinguishable from case 1. If measurement later shows this matters, batch the *intent* for a whole stage — never batch intent with its own commit.

**R7 — Rejected as too much for Phase 1.** Operation-level reconciliation and digest-bound approvals are both more machinery than a single-user demo needs. Accepted anyway: LC-P1-06 lists all three crash cases as acceptance criteria, and LC-P1-04 lists approvals bound to a digest and task id as P0. The honest counter-argument is scope, and it is answered by G2 exit criteria, not by weakening the contract.

**R8 — Single-writer assumption.** Phase 1 is local single-user. `writer_epoch` (A4) covers the Web-refresh-while-CLI-runs case but is not a substitute for real concurrency control. *Explicitly not claimed:* the design does not support multi-writer or multi-user, and LC-P1-05 requires user-level and future-multiuser scope to stay explicit.

## Contracts and acceptance tests

### C1 — Event vocabulary

Events are append-only, immutable, and closed. `events` rows carry:

| Column | Notes |
|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` — table-wide row identity only. Never used for ordering and never exposed as a Task-local number. |
| `seq` | `INTEGER NOT NULL` — **per-Task** gapless sequence, allocated inside the same transaction from `tasks.last_event_seq`; `UNIQUE(task_id, seq)` is the backstop. |
| `event_id` | `TEXT`, UUIDv7, `UNIQUE` |
| `task_id`, `run_id` | `task_id` always non-null. `run_id` is **nullable** and required only for `run.*`, `stage.*`, `operation.*`, `approval.*` and `checkpoint.*` events; Task-level events (`task_created`, `task_revised`) legitimately carry `run_id = NULL`, because a Task exists before its first Run and can be revised between Runs. Validate per event type, not per column. |
| `stage_id`, `operation_id` | nullable, but **both set** for any `operation.*` event |
| `type` | one of the closed enum below; unknown values are rejected, not coerced |
| `schema_version` | `INTEGER NOT NULL` |
| `occurred_at` | ISO-8601 UTC, informational only |
| `payload` | JSON, validated against the type's Pydantic model |

`type ∈ { task_created, task_revised, run_started, run_paused, run_resumed, run_finished,
stage_entered, stage_completed, stage_blocked,
operation_intent, operation_awaiting_approval, operation_attempted,
operation_confirmed, operation_failed, operation_uncertain, operation_reconciled,
approval_requested, approval_granted, approval_denied, approval_expired, approval_consumed,
checkpoint_created, artifact_recorded, source_changed, outbound_consent_requested }`

**Ordering invariant.** `seq` is the *only* order. `occurred_at` is never used to order anything — wall-clock is not monotonic and OpenHands' index is a better example of an ordering mechanism than its timestamps are.

**Why `seq` cannot be the rowid.** An earlier draft of this table specified `seq` as `INTEGER PRIMARY KEY AUTOINCREMENT` *and* `UNIQUE(task_id, seq)`. Those two clauses are not compatible. In SQLite an `INTEGER PRIMARY KEY` column **is** the rowid: it is unique across the whole table by construction, so consecutive values are distributed across Tasks rather than restarted per Task — Task A would hold `1, 2, 5` while Task B holds `3, 4`. No client resuming with `after_seq=<last_seen>` can then reason about one Task's contiguous tail, and the gaplessness this ADR exists to guarantee would be lost. Per-Task gaplessness requires a plain counter column allocated under the Task's own row, which is why `id` and `seq` are now separate: `id` is table-wide identity, `seq` is per-Task position. Corrected by [R-01](../acceptance/LC-P1-00-review-623e3ca.md); do not reintroduce `INTEGER PRIMARY KEY` on `seq`.

**State-transition invariant.** Every event that describes a change carries the state it moved *from* and *to*. Events without a transition (`artifact_recorded`, `source_changed`) are annotations that must not be used to reconstruct state.

### C2 — Operation state machine

```
                 policy=allow          commit(operation_attempted)
  PLANNED ───────────────────▶ AUTHORIZED ─────────────────────▶ ATTEMPTING
     │                              │                                  │
     │                        policy=ask                    commit(operation_confirmed,
     ▼                              ▼                            receipt + state)
  AWAITING_APPROVAL ─────▶ AUTHORIZED                            │
     │                       │                                  ▼
     │                       └──▶ DENIED (terminal)            CONFIRMED (terminal)
     ▼
  (approval_denied)                                                   │
                                                                     ▼
                                                               FAILED (terminal)

  ATTEMPTING (any operation, at any point)  ──[ process dies, or run is killed ]──▶
                                                                  UNCERTAIN
                                                                       │
                                            reconcile (read-only probe) 
                                                                       ▼
                              CONFIRMED | REPLAY_SAFE | FAILED | CONFLICT
```

**Crash behaviour, per state — the answer LC-P1-06 asks for:**

| State at crash | What is true | What recovery does |
|---|---|---|
| `PLANNED` / `AWAITING_APPROVAL` | No side effect was attempted. Intent may be durable, nothing was performed. | Nothing to reconcile. Resume the stage. The pending approval, if any, is evaluated for expiry on resume. |
| `AUTHORIZED` | Policy granted; `operation_intent` committed; the attempt had not begun. | Nothing to reconcile. Safe to attempt. |
| `ATTEMPTING` | `operation_attempted` committed. **The side effect may or may not have landed** — the DB cannot distinguish "died before the syscall" from "died after it". | **Enter `UNCERTAIN`.** Block the stage. Run reconciliation. **No replay without a resolution.** This is LC-P1-06 case 2. |
| `CONFIRMED` | `operation_confirmed` and the receipt committed together. The effect durably happened. | **Nothing to reconcile.** Re-emit the event for a lagging client. This is LC-P1-06 case 3, and the absence of work here is the point. |
| `UNCERTAIN` | Recorded, awaiting a probe. | Probe. Resolve. Never replay while unresolved. |
| `DENIED` / `FAILED` | Terminal. | Nothing. |

**Two guarantees that do the work:**

1. **`operation_attempted` commits before the side effect is attempted, in its own transaction.** Without this, a crash leaves no evidence that anything was in flight, and the system cannot distinguish case 1 from case 2 at all.
2. **`operation_confirmed` + the receipt + the state change commit in one transaction.** The filesystem is never inside a SQLite transaction and cannot be. That is precisely why the intent is written ahead and the outcome is confirmed behind.

### C3 — Transaction boundary

> One SQLite transaction contains: one or more `events` rows with contiguous `seq`, **and** all state-row updates those events describe, **and nothing else.**

- `BEGIN IMMEDIATE` (take the write lock up front; do not upgrade mid-transaction).
- Allocate `seq` from committed rows inside the transaction; the `UNIQUE(task_id, seq)` index is the backstop.
- Insert events, then update `tasks` / `runs` / `stages` / `operations` / `approvals` / `checkpoints` / `artifacts`.
- `COMMIT`.

A crash before `COMMIT` rolls back **both** the events and the state changes. The side effect, which is by definition outside the transaction, is the only thing that can survive a rollback — and it is covered by the write-ahead intent.

### C4 — Approval binding

`Approval` is a row, not a transient UI flag.

```
args_digest = SHA256( canonical_json({
    "schema_version": 1,
    "task_id":       <task_id>,
    "capability":    <registered capability id>,
    "resource_key":  <canonical resource identity>,
    "args":          <normalized arguments, keys sorted, no whitespace>,
    "depends_on":    <sorted content hashes of source material this op reads>,
}) )
```

Canonicalisation rules, fixed now so they cannot drift:

- Paths are resolved to real paths, then stored **workspace-relative, POSIX separators**, with drive letters and `..` segments removed. A path that cannot be canonicalised is a `deny`, not an `ask`.
- Argument keys are sorted; no timestamps, random values, or counters enter the digest. If an operation genuinely depends on one, it is passed out-of-band and the digest covers only the deterministic part.
- `depends_on` is the sorted list of content hashes of every source the operation reads. This is the mechanism by which "changed source invalidates downstream".

An approval is **valid** only when **all** hold: `state == granted`; `expires_at > now()`; `task_id` matches; the digest recomputed **at the moment of use** equals `args_digest`; the capability and `resource_key` match; the policy snapshot still equals current policy; and every hash in `depends_on` still matches the file on disk. It is **single-use**: consuming it moves it to `approval_consumed`.

**And the capability must be one the registry holds — checked where the consent is spent, not only where the verdict is made.** `args_digest` covers `<registered capability id>`, and C5 makes an unregistered id a `deny` at `policy.evaluate()`. For a long time that was the whole rule, which left the ordering — *evaluate, then consume* — as a sentence about callers rather than a constraint: `ApprovalLedger.consume()` and `ApprovalStore.consume()` both accepted any string, so an id that named no registered capability could be issued, granted and **consumed**, and the digest check would pass because the approval had been bound to that same fiction. Both now call `assert_capability_registered` first, before the row is read or spent. **C5 remains the first word**: this is the second choke point, not a replacement for the policy verdict — the two answer different questions, a verdict about whether this request may run and a refusal to spend a consent on a capability that cannot be described.

Refusal reasons are enumerated and machine-readable: `expired`, `consumed`, `task_scope_mismatch`, `args_changed`, `source_changed`, `policy_changed`, `not_granted`, `capability_unregistered`.

`capability_unregistered` is deliberately **not** `args_changed`. `args_changed` tells a caller to ask again for the right request, and asking again does not help a request that names a capability this build does not have. The vocabulary is watched against the enum by `tests/test_runtime_contracts.py::test_adr_c4_and_the_enum_are_one_vocabulary`, so this line and `ApprovalRefusal` cannot drift apart silently.

### C5 — Permission evaluation

```
evaluate(task_id, capability, resource_key, canonical_args) -> allow | ask | deny
```

- **Deny first.** Any matching `deny` returns `DENY` immediately. No later rule can upgrade it — no specificity override, no ordering escape. (This generalises deepagents' recursive-delete reasoning, which arrived at the same conclusion for the one case where first-match-wins was untenable.)
- Then `ask`: any matching `ask` returns `ASK`.
- Then `allow`: at least one matching `allow` returns `ALLOW`.
- **No matching rule returns `DENY`.** Default-deny. (Contrast deepagents' `return "allow"` and OpenHands' `NeverConfirm`.)

Inherited from A5, and required of the implementation:

- Both the declared path **and** its symlink/junction-resolved target are matched; a deny on either blocks. Absolute paths are mandatory at the boundary, so the documented relative-path bypass cannot occur.
- `ls`/`glob`-style bulk operations **filter** denied entries out of results rather than only refusing the call, so the model never learns a denied name existed.
- Deleting a directory is refused when any deny pattern matches it, its subtree, or any ancestor.
- Rule patterns are validated at load: absolute, no `..`, no `~`.

### C6 — Imported content cannot grant permission (structural, not textual)

1. `evaluate()` takes only application-supplied values. No parameter carries document text, excerpt text, or retrieval output. The decision is unreachable from imported content by construction.
2. Every capability's arguments are a closed Pydantic model with unknown keys **rejected**, and the rejection names the offending key and returns it to the model as a tool error (adopting deepagents' `_reject_unknown_keys` lesson from A6).
3. Imported text is carried in fields explicitly typed as untrusted content and are never parsed for policy. There is no policy-in-document parser, by construction rather than by convention.
4. Local-only analysis tools and outbound model requests are **distinct capabilities**, each independently scoped, so sending an excerpt to a provider is never a side effect of running a local computation.

### C7 — Acceptance tests

Concrete, executable assertions. `AT-*` map to the three LC-P1-06 crash cases and the LC-P1-04 requirements.

**Event and state coupling (LC-P1-05)**

- `test_event_and_state_rollback_together` — inject a fault after the event INSERT but before the state UPDATE. Assert both the new `events` rows and the target row's state are unchanged.
- `test_seq_is_gapless_under_fault_injection` — 1000 transactions each faulting at a different step; assert `seq` forms `1..1000` with no duplicates and **no gaps**. This is the direct contrast with OpenHands' `test_event_log_index_gaps_detection`.
- `test_foreign_keys_pragmas_enabled` — assert `PRAGMA foreign_keys == 1` (see R2).
- `test_concurrent_writers_get_unique_seq` — N threads appending; assert `seq` is a permutation of `1..N`.

**Crash recovery (LC-P1-06)**

- `AT-1 test_crash_before_write_is_replayable` — fault before the `operation_attempted` commit. Assert: no `UNCERTAIN` is created, the stage resumes, replay proceeds, and the output file is written exactly once.
- `AT-2 test_crash_after_write_before_commit_marks_uncertain_and_blocks_replay` — fault in the window **after** the filesystem write and **before** `COMMIT`. Assert: `operation.state == UNCERTAIN`; `store.replay(operation_id)` raises `ReconciliationRequired`; **a write counter proves no second write occurred**; the stage is blocked.
- `AT-3 test_crash_after_commit_before_ui_receipt_needs_no_replay` — run to `CONFIRMED`, then drop the notification. Assert: no `UNCERTAIN`; **no second write** (write counter still 1, file mtime and hash unchanged); a client reconnecting with `after_seq=<last_seen>` receives exactly the missed events.
- `AT-4 test_reconciliation_confirms_landed_write_without_rewriting` — crash after the write; probe finds the file with a matching content hash. Assert: `CONFIRMED`, `operation_reconciled` recorded with `resolution='confirmed_by_probe'`, and the write counter is still 1.
- `AT-5 test_reconciliation_detects_absent_write` — crash before the write; probe finds nothing. Assert: `REPLAY_SAFE`; replay permitted; write counter 2.
- `AT-6 test_reconciliation_flags_conflicting_content_for_human` — probe finds a file at the canonical path whose hash differs. Assert: `CONFLICT`; replay refused; no automatic resolution.
- `AT-7 test_crash_matrix_subprocess` — a subprocess is `kill -9`'d at each of the three injection points; after restart, assert the invariant table in C2 holds in every case.

**Approval binding (LC-P1-04)**

- `test_approval_rejected_when_arguments_change` — grant for content `"x"`; attempt with `"y"`. Assert refused, reason `args_changed`.
- `test_approval_rejected_on_task_scope_mismatch` — granted in task A, attempted in task B. Assert refused, reason `task_scope_mismatch`.
- `test_expired_approval_is_not_reusable` — `expires_at` in the past. Assert refused, reason `expired`.
- `test_approval_is_single_use` — identical arguments attempted twice. Assert the second is refused, reason `consumed`.
- `test_approval_invalidated_by_source_change` — `depends_on` holds hash H1; the file is modified to H2. Assert refused, reason `source_changed`.

**Permission evaluation (LC-P1-04)**

- `test_deny_beats_allow_and_ask` — matching `deny` and `allow` rules. Assert `DENY`. Direct contrast with deepagents' `test_earlier_allow_wins_over_later_catch_all_deny`.
- `test_ask_beats_allow` — assert `ASK`.
- `test_default_is_deny` — no matching rule. Assert `DENY`.
- `test_source_root_is_read_only_before_any_syscall` — a write whose canonical path resolves under a source root. Assert refused **and**, via a filesystem spy, that **zero write syscalls were attempted** — refusal precedes the effect.
- `test_symlink_into_source_root_is_denied` — assert both declared and resolved paths are checked.
- `test_bulk_list_filters_denied_entries` — denied entries absent from results, not merely refused.
- `test_traversal_variants_are_refused` — `../`, percent-encoded `%2e%2e%2f`, absolute Windows paths, and a junction, each asserted `DENY`.
- `test_delete_refused_when_descendant_denied` — port of deepagents' `test_recursive_delete_refused_when_descendant_denied`, asserting the behaviour now holds for *all* operations, not just delete.
- `test_permission_rules_reject_bad_patterns` — `..`, `~`, and relative rule paths rejected at load.

**Anti-injection (LC-P1-04)**

- `test_injected_document_cannot_create_a_rule` — a source document contains `ALLOW: write to /etc/passwd` and the model is induced to act on it. Assert: no rule is created; the decision is identical to the decision with the document absent.
- `test_policy_input_surface_is_closed` — assert via `inspect.signature(evaluate)` that no parameter can carry document or excerpt text. A structural test, not a behavioural one.
- `test_unknown_argument_keys_are_rejected` — a tool call with an invented key is refused with an error naming the key.
- `test_outbound_excerpt_requires_scoped_consent` — any network transmission is refused unless a matching approval exists, and the approval digest covers the exact excerpt set sent.

**Client recovery (LC-P1-12 interaction)**

- `test_client_resumes_from_after_seq` — a client that saw events `1..k` receives exactly `k+1..N` and nothing else.

## Re-evaluation trigger

Revisit this ADR if any of the following occurs:

1. **Multi-writer or multi-user scope enters Phase 1.** The single-writer + `writer_epoch` design (R8) is the weakest part of the durability story and would be replaced by real transactional concurrency control, likely invalidating C3.
2. **Phase 1 gains an arbitrary-code or shell capability.** LC-P1-04 forbids it, and this ADR's permission model was designed around a closed capability registry. An open execution surface would require resource limits that path-glob rules cannot express.
3. **SQLite proves inadequate under measured load** (event volume, concurrent readers on the Web event stream). The fallback is not "move to Postgres" — it is reconsidering whether the UI needs a server-side projection, which would let the client read a materialized view instead of tailing `seq`.
4. **A capability needs sub-call granularity** — a deterministic analysis operator whose internal steps each need independent policy. The resource key is currently `(capability, resource_key, args_digest)`; finer granularity would need a nested argument-digest scheme.
5. **Reconciliation proves unreliable in practice.** If `CONFLICT` or spurious `REPLAY_SAFE` outcomes are frequent, the probe design needs revisiting — most likely by requiring operations to write a deliberate intent marker (a temp file renamed into place, or a pre-written receipt) so reconciliation compares against app-written evidence rather than inferring from the filesystem.
6. **A real benchmark contradicts a claim in this ADR.** Specifically: if a measurement shows the write-ahead intent's extra transaction dominates Phase 1 runtime, revisit R6 by batching intents per stage — never by batching intent with its own commit.
