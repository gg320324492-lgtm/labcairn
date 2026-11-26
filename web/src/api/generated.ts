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

export type ApplyReviewBody = {
  project_id: string
  input_version_id: string
  source_root_id: string
  source_key: string
  output_label: string
  window_end: string
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
  grant_policy_digest?: string | null
  bound_sources?: BoundSource[]
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

export type BoundSource = {
  schema_version?: number
  resource_key: string
  expected_hash: string
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

export type ChainComment = {
  feedback_id: string
  issue_key: string
  version_id: string
  comment_text: string
  anchor_text: string | null
  anchor_status: string
  anchor_reason: string | null
}

export type ChainEdge = {
  edge_id: string
  parent_version_id: string
  child_version_id: string
}

export type ChainEdit = {
  edit_action_id: string
  feedback_id: string | null
  version_edge_id: string
  actor_kind: string
  grade: string
}

export type CheckKind = 'c1' | 'c2' | 'c3' | 'c4'

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

export type ClaimExtractionBody = {
  source_id: string
  locator_key: string
  user_id: string
  provider: string
  model: string
  destination: string
  subject_ref: string
  purpose?: string
  approval_id?: string | null
}

export type ClaimRecorded = {
  record: EvidenceRecord
  anchor_id: string
}

export type CommentResponses = {
  feedback_id: string
  states: string[]
}

export type ComputationLocator = {
  locator_kind?: 'computation'
  operator_id: string
  operator_version: string
  parameters?: Record<string, JsonValue>
  input_hashes: string[]
}

export type DeliverableFileWire = {
  kind: string
  relative_path: string
  content_base64: string
  sha256: string
  size_bytes: number
}

export type DeliverablesExportWire = {
  project_id: string
  dossier_artifact_id: string
  task_id: string
  input_version_id: string
  output_version_id: string
  marked_receipt_id: string
  clean_receipt_id: string
  edge_id: string
  deliverables: DeliverableFileWire[]
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
  | 'operation_denied'
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
  | 'model_exchanged'

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
  identifier_ids?: string[]
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

export type GuidanceCheck = {
  check_id: string
  question: string
  pass_criterion: string
  state: string
  proposed_by: string
  proposed_at: string
  confirmed_by: string | null
  confirmed_at: string | null
  resolution_reason: string | null
}

export type GuidanceRule = {
  rule_id: string
  version: number
  issue_type: string
  statement: string
  context: string
  scope: string
  example: string
  state: string
  proposed_by: string
  proposed_at: string
  confirmed_by: string | null
  confirmed_at: string | null
  resolution_reason: string | null
  sources: string[]
  counterexamples: RuleCounterexample[]
  checks: GuidanceCheck[]
  shared_scope?: string
  published_by?: string | null
  published_at?: string | null
}

export type GuidanceRulePublishBody = {
  user_id: string
}

export type GuidanceRuleVerdictBody = {
  verdict: 'confirmed' | 'disputed'
  user_id: string
  reason?: string
}

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

export type ImportReceipt = {
  receipt_id: string
  task_id: string
  source_id: string
  source_root_id: string
  source_key: string
  relative_path: string
  original_sha256: string
  size_bytes: number
  imported_at: string
}

export type InterruptedPublication = {
  operation_id: string
  import_receipt: ImportReceipt
  copy_key: string
  publication_key: string
  manifest_key: string
  publication_artifact_id: string
  import_artifact_id: string
  edited_sha256: string
}

export type InterruptedReplayBody = {
  edited_base64: string
  approval_id: string
}

export type InterruptedResolutionWire = {
  operation_id: string
  resolution: string
  resulting_state: string
  replay_permitted: boolean
  expected_sha256: string
  observed_sha256: string | null
  resource_key: string
  detail: string
}

export type InterruptedResolveBody = {
  expected_sha256: string
}

export type IssueData = {
  issue_id: string
  project_id: string
  task_id: string | null
  version_id: string | null
  feedback_id: string | null
  step: string
  error_text: string
  duration_seconds: number | null
  retry_count: number | null
  severity: string
  category: string
  reported_by: string
  reported_at: string
  status: string
  fix_version: string | null
  regression_note: string | null
}

export type IssueKeys = {
  project_id: string
  issue_keys: string[]
}

export type IssueRecordBody = {
  issue_id: string
  project_id: string
  task_id?: string | null
  version_id?: string | null
  feedback_id?: string | null
  step: string
  error_text: string
  duration_seconds?: number | null
  retry_count?: number | null
  severity: 'blocker' | 'serious' | 'minor' | 'suggestion'
  category: 'function' | 'interface' | 'performance' | 'model' | 'documentation'
  reported_by: string
}

export type IssueStatusBody = {
  project_id: string
  status: 'confirmed' | 'fixed' | 'wontfix'
  fix_version?: string | null
  regression_note?: string | null
}

export type IssueStatusUpdate = {
  issue: IssueData
}

export type JsonValue = unknown

export type MeetingHit = {
  record_id: string
  project_id: string
  source_sha256: string
  record_format: string
  record_index: number
  timestamp_label: string | null
  record_fingerprint: string
  text: string
  locator_json: string
  ingested_at: string
}

export type MeetingIngestBody = {
  project_id: string
  root_id: string
  resource_key: string
}

export type MeetingTextIngested = {
  project_id: string
  source_sha256: string
  records_indexed: number
  entry_records: number
  paragraph_records: number
  limitations_recorded: number
  ingested_at: string
}

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

export type PptDeckIngested = {
  project_id: string
  source_sha256: string
  objects_indexed: number
  title_objects: number
  body_objects: number
  notes_objects: number
  table_objects: number
  image_objects: number
  limitations_recorded: number
  ingested_at: string
}

export type PptHit = {
  object_id: string
  project_id: string
  source_sha256: string
  slide_no: number
  object_position: number
  object_kind: string
  object_fingerprint: string
  text: string
  media_target: string | null
  locator_json: string
  ingested_at: string
}

export type PptIngestBody = {
  project_id: string
  root_id: string
  resource_key: string
}

export type PreviewEditSummary = {
  feedback_id: string
  part: string
  paragraph: number
  old_text: string
  new_text: string
  author: string
}

export type ProjectGraph = {
  version_ids: string[]
  edges: ChainEdge[]
}

export type ProposalAcceptanceBody = {
  user_id: string
  verdict: string
  note?: string
}

export type ProposalSettled = {
  proposal: EvidenceRecord
  confirmation: EvidenceRecord
  verdict: string
  user_id: string
}

export type QualityCheckFact = {
  check: string
  detail: string
  feedback_id?: string | null
  paragraph?: number | null
  expected?: string | null
  actual?: string | null
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

export type ReviewApplyCancelBody = {
  project_id: string
  reason: string
}

export type ReviewApplyCancelled = {
  project_id: string
  reason: string
  accepted: boolean
}

export type ReviewApplyResult = {
  project_id: string
  input_version_id: string
  output_version_id: string
  edge_id: string
  marked_receipt_id: string
  marked_sha256: string
  clean_receipt_id: string
  clean_sha256: string
  dossier_artifact_id: string
  applied: string[]
  handovers: ReviewHandover[]
  unresolved: ReviewUnresolved[]
  quality?: RoundQualityReport | null
}

export type ReviewDecisionBody = {
  project_id: string
  feedback_id: string
  verdict: 'accepted' | 'partly_accepted' | 'rejected' | 'pending'
  operator: string
  needs_evidence?: boolean
}

export type ReviewDecisionData = {
  verdict: string
  needs_evidence: boolean
  operator: string
  decided_at: string
}

export type ReviewHandover = {
  feedback_id: string
  reason: string
  detail: string
  handover: string
}

export type ReviewManuscript = {
  project_id: string
  version_id: string
  sha256: string
  paragraphs: ReviewParagraph[]
}

export type ReviewOpinion = {
  feedback_id: string
  issue_key: string
  version_id: string
  comment_text: string
  author: string | null
  anchor_status: string
  anchor_reason: string | null
  anchor_paragraph: number | null
  anchor_start: number | null
  anchor_end: number | null
  anchor_text: string | null
  comment_locator: Record<string, unknown> | null
  location_state: string
  suggestion: ReviewSuggestionData | null
  decision: ReviewDecisionData | null
  response_states: string[]
}

export type ReviewOpinions = {
  project_id: string
  version_id: string
  opinions: ReviewOpinion[]
}

export type ReviewParagraph = {
  index: number
  text: string
}

export type ReviewPreview = {
  project_id: string
  input_version_id: string
  applied: number
  pending: number
  rejected: number
  affected_paragraphs: number[]
  edits: PreviewEditSummary[]
  marked_sha256: string
  marked_size_bytes: number
  clean_sha256: string
  clean_size_bytes: number
  original_sha256: string
  original_size_bytes: number
}

export type ReviewRoundListed = {
  project_id: string
  version_id: string
  created_at: string
}

export type ReviewSuggestBody = {
  project_id: string
  version_id: string
  mode?: 'real' | 'substitute'
  approval_ids?: Record<string, string>
  max_requests?: number | null
  max_tokens?: number | null
  max_consecutive_failures?: number
  retry_attempts?: number
}

export type ReviewSuggestRun = {
  run_id: string
  project_id: string
  version_id: string
  mode: string
  model_id: string
  requests_made: number
  tokens_estimated: number
  stopped_reason: string | null
  suggestions_recorded: number
  opinions_skipped: number
  started_at: string
  finished_at: string
  duration_seconds: number
  requests?: SuggestionRequestEntry[]
}

export type ReviewSuggestionBody = {
  project_id: string
  version_id: string
  feedback_id: string
  part: string
  paragraph: number
  old_text: string
  new_text: string
  author: string
}

export type ReviewSuggestionData = {
  part: string
  paragraph: number
  old_text: string
  new_text: string
  author: string
  proposed_at: string
}

export type ReviewUnresolved = {
  feedback_id: string
  reason: string
  detail: string
}

export type RevisionPublished = {
  publication: ArtifactReceipt
  publication_key: string
  publication_sha256: string
  operation: Operation
  stage: Stage
  approval: Approval
}

export type RoleClaimJudgement = {
  text: string
  kind: string
  evidence_ref?: string | null
  issue_key?: string | null
  advisor_quote?: string | null
}

export type RoleCritiqueJudgement = {
  verdict: string
  repair_advice: string
  handover_reason?: string | null
}

export type RoleGuidanceJudgement = {
  issue_type: string
  severity: string
  reason: string
  suggested_next_action: string
  uncertainty_kind: string
  what_is_uncertain: string
  claims?: RoleClaimJudgement[]
  style_notes?: string[]
}

export type RoleRunBody = {
  roles: string[]
  project_id: string
  issue_key: string
  version_ids?: string[]
  rule_id?: string | null
  evidence_refs?: string[] | null
  trajectory?: RoleTrajectoryJudgement | null
  guidance?: RoleGuidanceJudgement | null
  critique?: RoleCritiqueJudgement | null
  provider?: string | null
  model?: string | null
  root_id?: string | null
  resource_key?: string | null
  material_ref?: string | null
  purpose?: string | null
  destination?: string | null
  subject_ref?: string | null
  expires_at?: string | null
  approval_id?: string | null
}

export type RoleRunCandidate = {
  role_id: string
  role_version: number
  issue_key: string
  issue_type: string
  edit_action_id: string | null
  alignment: string
  advisor_quote: string
  note: string
}

export type RoleRunCard = {
  role_id: string
  role_version: number
  target_locator: string
  issue_type: string
  severity: string
  reason: string
  evidence_refs: string[]
  suggested_next_action: string
  uncertainty: RoleRunUncertainty
  claims?: RoleRunCardClaim[]
  style_notes?: string[]
  rule_refs?: RoleRunRuleCitation[]
  historical_case_refs?: string[]
  counterexamples_or_limits?: string[]
}

export type RoleRunCardClaim = {
  text: string
  kind: string
  evidence_ref?: string | null
  issue_key?: string | null
  advisor_quote?: string | null
}

export type RoleRunRuleCitation = {
  rule_id: string
  version: number
  statement: string
  counterexamples?: string[]
}

export type RoleRunRun = {
  roles: string[]
  answer: string | null
  exchange_event_id: string | null
  candidate?: RoleRunCandidate | null
  card?: RoleRunCard | null
  verdict?: RoleRunVerdict | null
}

export type RoleRunTicketWire = {
  roles: string[]
  contracts: Record<string, unknown>[]
  prompt: string
  excerpts: string[]
  material: Record<string, string>
  plan: Record<string, string>
  approval_id: string | null
  asked_at: string
}

export type RoleRunUncertainty = {
  kind: string
  what_is_uncertain: string
  missing?: string[]
}

export type RoleRunVerdict = {
  role_id: string
  role_version: number
  reviewed_locator: string
  reviewed_issue_type: string
  verdict: string
  grade: string
  counter_evidence?: RoleRunRuleCitation[]
  repair_advice: string
  handover_reason: string | null
}

export type RoleTrajectoryJudgement = {
  issue_type: string
  alignment: string
  advisor_quote: string
  note: string
  edit_action_id?: string | null
}

export type RoundQualityReport = {
  project_id: string
  input_version_id: string
  output_version_id: string
  dossier_artifact_id: string
  checks: labcairn__application__quality_checks__CheckOutcome[]
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

export type RuleCounterexample = {
  statement: string
  issue_key: string | null
  recorded_by: string
  recorded_at: string
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

export type SourceKind =
  'pdf' | 'markdown' | 'text' | 'csv' | 'xlsx' | 'docx' | 'pptx' | 'meeting_text' | 'other'

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

export type SuggestionRequestEntry = {
  feedback_id: string
  source: string
  outcome: string
  attempts: number
  elapsed_s: number
  tokens_estimated: number
  tokens_measured: number
  detail: string
  retryable: boolean | null
  approval_id: string | null
  approval_spent: boolean
}

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

export type TaskSelectBody = {
  task_id: string
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

export type Trajectory = {
  comments: ChainComment[]
  edits: ChainEdit[]
  responses: CommentResponses[]
}

export type TrajectoryHit = {
  trajectory_id: string
  project_id: string
  entry_kind: string
  feedback_id: string | null
  edit_action_id: string | null
  revision_event_id: string | null
  version_id: string
  issue_key: string | null
  comment_text: string | null
  anchor_text: string | null
  anchor_paragraph: number | null
  verdict: string | null
  change_kind: string | null
  change_text: string | null
  text_digest: string
  source_version_id: string
  source_locator: string
  source_sha256: string
  ingested_at: string
}

export type TrajectoryIngestBody = {
  project_id: string
  ingested_at?: string | null
}

export type TrajectoryIngested = {
  project_id: string
  entries_indexed: number
  comment_entries: number
  edit_entries: number
  skipped_versions: number
  ingested_at: string
}

export type UsableRule = {
  rule_id: string
  version: number
  name: string
  summary: string
  scope: string
  state: string
  sources: string[]
  confirmed_by: string | null
  confirmed_at: string | null
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
  outcome: labcairn__evidence__states__CheckOutcome
  detail: string
  checked_at: string
  normalization_profile?: NormalizationProfile | null
}

export type VerificationStatus =
  'planned' | 'extracted' | 'verified_by_rule' | 'user_attested' | 'conflicted' | 'unsupported'

export type labcairn__application__quality_checks__CheckOutcome = {
  check: string
  passed: boolean
  facts?: QualityCheckFact[]
}

export type labcairn__evidence__states__CheckOutcome =
  'pass' | 'fail' | 'indeterminate' | 'not_checked'
