// GENERATED FILE. Do not edit it by hand, and do not run prettier over it.
//
// It is generated from the API's OpenAPI document, which is generated from the
// application layer's response models:
//
//     uv run python -m labcairn.api.typescript web/src/api/generated.ts
//
// `tests/test_api.py` compares this file with the document the Python models
// produce now, so a model that changes without this file being regenerated is
// a failing test rather than a stale type. The generator writes the
// formatting too -- the repository's prettier settings, with no semicolons,
// single quotes and a hundred-column width -- so that a regeneration does
// not produce a file that prettier would then rewrite.

export type AnalysisBody = {
  root_id: string
  path: string
  operator_id: string
  recipe: string
  parameters?: Record<string, unknown>
  approval_id: RawId
}

export type Approval = {
  schema_version?: number
  approval_id?: RawId
  task_id: RawId
  operation_id: RawId
  capability: string
  resource_key: string
  args_digest: string
  state?: ApprovalState
  expires_at: string
  granted_at?: string | null
  consumed_at?: string | null
}

export type ApprovalBody = {
  capability: CapabilityId
  arguments?: Record<string, unknown>
  root_id: string
  resource_key: string
  depends_on?: string[]
  expires_at: string
  run_id?: RawId | null
  stage_name?: string
}

export type ApprovalConsumed = {
  approval: Approval
  operation: Operation | null
}

export type ApprovalGranted = {
  approval: Approval
}

export type ApprovalRequested = {
  operation: Operation
  approval: Approval
}

export type ApprovalState = 'pending' | 'granted' | 'denied' | 'consumed' | 'expired'

export type ApprovalUseBody = {
  capability: CapabilityId
  arguments?: Record<string, unknown>
  root_id: string
  resource_key: string
  depends_on?: string[]
}

export type ArtifactKind = 'report' | 'figure' | 'table' | 'dataset' | 'manifest' | 'other'

export type ArtifactProducerKind = 'stage' | 'analysis_operator' | 'user' | 'model'

export type ArtifactReceipt = {
  schema_version?: number
  receipt_id: string
  task_id: string
  kind: ArtifactKind
  relative_path: string
  content_sha256: string
  size_bytes: StrictNonNegInt
  revision?: StrictPosInt
  produced_by: ArtifactProducerKind
  producer_id: string
  derived_from?: DerivationRef[]
  staleness?: ArtifactStaleness
  staleness_reason?: string | null
  media_type?: string | null
  created_at: string
}

export type ArtifactStaleness = 'current' | 'stale'

export type ArtifactView = {
  receipt: ArtifactReceipt
  resource_key: string
}

export type CapabilityId =
  | 'fs.read'
  | 'fs.list'
  | 'fs.write'
  | 'fs.delete'
  | 'source.read'
  | 'source.inventory'
  | 'retrieval.query'
  | 'analysis.run'
  | 'artifact.write'
  | 'report.render'
  | 'model.request'

export type CheckKind = 'c1' | 'c2' | 'c3' | 'c4'

export type CheckOutcome = 'pass' | 'fail' | 'indeterminate' | 'not_checked'

export type ClaimBody = {
  source_id: string
  locator_key: string
  kind?: EvidenceKind
  text?: string | null
  span?: string | null
  value?: number | null
  unit?: string | null
  tolerance?: number | null
}

export type ClaimRecorded = {
  record: EvidenceRecord
  anchor_id: string
}

export type ComputationLocator = {
  locator_kind?: 'computation'
  operator_id: string
  operator_version: string
  parameters?: Record<string, JsonValue>
  input_hashes: string[]
}

export type DerivationRef = {
  target_kind: DerivationTargetKind
  target_id: string
  content_sha256?: string | null
}

export type DerivationTargetKind =
  'evidence_record' | 'source' | 'source_anchor' | 'artifact' | 'material_file'

export type Event = {
  schema_version?: number
  event_id?: RawId
  seq: StrictPosInt
  task_id: RawId
  run_id?: RawId | null
  stage_id?: RawId | null
  operation_id?: RawId | null
  type: EventType
  transition?: EventTransition | null
  payload?: Record<string, unknown>
  occurred_at?: string
}

export type EventStreamPage = {
  schema_version?: number
  task_id: RawId
  events: Event[]
  next_after_seq: StrictNonNegInt
  caught_up?: boolean
}

export type EventTransition = {
  schema_version?: number
  from_state: string
  to_state: string
}

export type EventType =
  | 'task_created'
  | 'task_revised'
  | 'run_started'
  | 'run_paused'
  | 'run_resumed'
  | 'run_finished'
  | 'stage_entered'
  | 'stage_completed'
  | 'stage_blocked'
  | 'operation_intent'
  | 'operation_awaiting_approval'
  | 'operation_attempted'
  | 'operation_confirmed'
  | 'operation_failed'
  | 'operation_uncertain'
  | 'operation_reconciled'
  | 'approval_requested'
  | 'approval_granted'
  | 'approval_denied'
  | 'approval_expired'
  | 'approval_consumed'
  | 'checkpoint_created'
  | 'artifact_recorded'
  | 'source_changed'
  | 'outbound_consent_requested'
  | 'feedback_recorded'
  | 'edit_action_recorded'
  | 'response_recorded'
  | 'followup_assessed'

export type EvidenceCreator = 'rule' | 'user' | 'model_proposal'

export type EvidenceKind = 'claim' | 'numeric' | 'result'

export type EvidenceRecord = {
  schema_version?: number
  evidence_id: string
  task_id: string
  kind: EvidenceKind
  text: string | null
  value?: StrictFloat | null
  unit?: string | null
  tolerance?: StrictNonNegFloat | null
  anchor_ids?: string[]
  extracted_span?: string | null
  extracted_span_sha256?: string | null
  status: VerificationStatus
  verification_log?: VerificationRecord[]
  created_by: EvidenceCreator
  created_by_id: string
  source_content_hash?: string | null
  created_at: string
  superseded_by?: string | null
}

export type FigureRun = {
  source: Source
  selection: Selection
  result: Record<string, unknown>
  result_kind: string
  manifest: ReproducibilityManifest
  manifest_receipt: ArtifactReceipt
  figure_receipt: ArtifactReceipt | null
}

export type FileRef = {
  schema_version?: number
  relative_path: string
  content_sha256: string
}

export type FilterOp = 'eq' | 'ne' | 'gt' | 'ge' | 'lt' | 'le'

export type HTTPValidationError = {
  detail?: ValidationError[]
}

export type Health = {
  status: string
  host: string
  port: number
  origins: string[]
  task_id: string
}

export type JsonValue = unknown

export type MissingPolicy = 'exclude' | 'refuse'

export type NormalizationProfile =
  | 'exact'
  | 'nfkc_whitespace_collapsed'
  | 'nfkc_whitespace_collapsed_ligatures'
  | 'word_boundaries_removed'

export type Operation = {
  schema_version?: number
  operation_id?: RawId
  task_id: RawId
  run_id: RawId
  stage_id: RawId
  state?: OperationState
  capability: string
  resource_key: string
  depends_on?: string[]
  args_digest: string
}

export type OperationState =
  | 'planned'
  | 'awaiting_approval'
  | 'authorized'
  | 'denied'
  | 'attempting'
  | 'confirmed'
  | 'failed'
  | 'uncertain'

export type PlanStage = {
  stage: StageName
  status: StageStatus
  blocked_reason?: string | null
}

export type RawId = string

export type RawSourceId = string

export type RefusalBody = {
  reason: string
  message: string
}

export type RenderEnvironment = {
  schema_version?: number
  matplotlib_version: string
  svg_hashsalt: string
  font_families: string[]
  platform: string
}

export type ReportBody = {
  path: string
  template_id: string
}

export type ReportRendered = {
  receipt: ArtifactReceipt
  resource_key: string
}

export type ReproducibilityManifest = {
  schema_version?: number
  input_file: FileRef
  operator: string
  locator: ComputationLocator
  recipe: FileRef
  output: JsonValue
  output_sha256: string
  environment: RenderEnvironment
}

export type RowFilter = {
  column: string
  op: FilterOp
  value: string
}

export type RowRange = {
  start: number
  end: number
}

export type RowSet = {
  rows: number[]
}

export type Run = {
  schema_version?: number
  run_id?: RawId
  task_id: RawId
  status?: RunStatus
  attempt?: StrictPosInt
  started_at?: string | null
  finished_at?: string | null
}

export type RunStatus = 'pending' | 'running' | 'paused' | 'finished' | 'abandoned'

export type Selection = {
  source_id: string
  content_sha256: string
  columns: string[]
  rows: RowRange | RowSet | RowFilter
  missing: MissingPolicy
}

export type SessionInfo = {
  token: string
  path: string
}

export type Source = {
  schema_version?: number
  source_id: string
  kind: SourceKind
  display_name: string
  relative_path: string
  content_sha256: string
  size_bytes: StrictNonNegInt
  readability?: SourceReadability
  readability_disclosure?: string | null
  identifiers?: SourceIdentifier[]
  ingested_at: string
}

export type SourceAddress = {
  source_id: string
  locator_key: string
  locator_kind: string
  extraction_version: string
  text: string
}

export type SourceIdentifier = {
  kind: SourceIdentifierKind
  value: string
}

export type SourceIdentifierKind = 'doi' | 'arxiv' | 'isbn' | 'local'

export type SourceKind = 'pdf' | 'markdown' | 'text' | 'csv' | 'xlsx' | 'docx' | 'other'

export type SourceReadability = 'readable' | 'unreadable_no_ocr' | 'unparseable'

export type SourceView = {
  source: Source
  resource_key: string
}

export type Stage = {
  schema_version?: number
  stage_id?: RawId
  task_id: RawId
  run_id: RawId
  name: string
  status?: StageStatus
  input_hashes?: string[]
  output_hashes?: string[]
  blocked_reason?: string | null
}

export type StageBody = {
  stage_name: string
  capability: CapabilityId
  arguments?: Record<string, unknown>
  root_id: string
  resource_key: string
  run_id?: RawId | null
  approval_id?: RawId | null
  depends_on?: string[]
}

export type StageName =
  'intake' | 'inventory' | 'retrieve' | 'evidence' | 'propose' | 'draft' | 'validate' | 'deliver'

export type StageRun = {
  run: Run
  stage: Stage
  operation: Operation
  approval: Approval | null
  artifacts: ArtifactReceipt[]
}

export type StageStatus = 'pending' | 'entered' | 'blocked' | 'completed' | 'failed'

export type StrictFloat = number

export type StrictNonNegFloat = number

export type StrictNonNegInt = number

export type StrictPosInt = number

export type Task = {
  schema_version?: number
  task_id?: RawId
  title: string
  goal: TaskGoal
  bound_source_ids?: RawSourceId[]
  revision?: StrictPosInt
  created_at?: string
  updated_at?: string
}

export type TaskGoal = {
  schema_version?: number
  objective: string
  success_criterion: string
}

export type TaskPlan = {
  task_id: RawId
  skill_id: string
  skill_digest: string
  steps: PlanStage[]
}

export type TaskState = {
  task: Task
  runs: Run[]
  stages: Stage[]
  artifacts: ArtifactReceipt[]
  approvals: Approval[]
  last_event_seq: number
}

export type TaskStep = {
  stage: Stage
  attempt: number
}

export type ValidationError = {
  loc: (string | number)[]
  msg: string
  type: string
  input?: unknown
  ctx?: Record<string, never>
}

export type VerificationRecord = {
  schema_version?: number
  check: CheckKind
  checker_id: string
  outcome: CheckOutcome
  detail: string
  checked_at: string
  normalization_profile?: NormalizationProfile | null
}

export type VerificationStatus =
  'planned' | 'extracted' | 'verified_by_rule' | 'user_attested' | 'conflicted' | 'unsupported'
