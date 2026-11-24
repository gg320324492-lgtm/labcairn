/**
 * The API paths the workbench uses.
 *
 * One list, so that two things can be checked against it: the drift check
 * compares every path here with a route the service actually declares, and the
 * proxy's mount point is the one place the development server's rewrite is
 * written down.
 *
 * The paths are the service's, not ours. They are written as the service
 * declares them — `/task` and not `/tasks/current`, `/plan` and not
 * `/task/plan` — because a path the service does not serve is a 404 that
 * looks like an empty workspace.
 *
 * **The event stream is among them, and it is a second way to read the
 * same log, not a second source of truth.** The service's stream carries
 * events — facts about what happened — and never commands, so a reconnecting
 * client can ask for what it missed and cannot ask for anything to be done.
 * The workbench's state panel still reads `/task` on every render; the
 * events panel reads the stream and shows the cursor it resumed from, so a
 * reader can tell the two apart: one is the task as it stands, the other is
 * how it got there.
 */

import type { ApplyReviewBody, MeetingIngestBody, PptIngestBody } from './generated'

/** The paths the workbench reads, keyed by what they are for. */
export const API_PATHS = {
  /** What the service is, and where it listens. */
  health: '/health',
  /** The token a client presents, and where the token was written. */
  session: '/session',
  /** Every task in this workspace's store. */
  tasks: '/tasks',
  /** The task, its runs, its stages, its artefacts and its approvals. */
  task: '/task',
  /** The declared workflow and how far this task has got through it. */
  plan: '/plan',
  /** The runtime stages the store holds. */
  steps: '/steps',
  /** The material this task is bound to. */
  sources: '/sources',
  /** The artefacts this task has produced. */
  artifacts: '/artifacts',
  /** The task's events, delivered as a server-sent event stream. */
  eventsStream: '/events/stream',
  /** Bind the service to another task in this workspace. */
  taskSelect: '/task/select',
  /** The ledger's records for this task, each saying whose words it is. */
  records: '/records',
  /** The guidance rules the memory holds, each with its counterexamples. */
  guidanceRules: '/guidance/rules',
  /** One issue's advisor trajectory: the comments, the edits and the states. */
  trajectory: '/trajectory',
  /** A paper project's versions and the accepted edges between them. */
  trajectoryGraph: '/trajectory/graph',
  /** The issue keys a paper project's chain holds: what there is to look at. */
  issueKeys: '/trajectory/issue-keys',
  /** One review round's opinions, with their suggestions and verdicts. */
  reviewOpinions: '/review/opinions',
  /** One review round's manuscript, in the anchors' own numbering. */
  reviewManuscript: '/review/manuscript',
  /** One suggestion the model proposed, as a record and not a decision. */
  reviewSuggestion: '/review/suggestion',
  /** Run the suggestion loop over one version's pending opinions. */
  reviewSuggest: '/review/suggest',
  /** The reviewer's verdict on one opinion's suggestion. */
  reviewDecision: '/review/decision',
  /** Apply the stored, approved set and close the round. */
  reviewApply: '/review/apply',
  /** Measure what the apply round would do, before anything is written. */
  reviewPreview: '/review/preview',
  /** The four deliverables of one closed binding, in one export. */
  reviewDeliverables: '/review/deliverables',
  /** The advisor trajectory's full-text search, answered with its provenance. */
  trajectorySearch: '/trajectory/search',
  /** The slide deck index's full-text search, answered with its provenance. */
  pptSearch: '/ppt/search',
  /** Index one deck's objects, read through the same gate every reader uses. */
  pptIngest: '/ppt/ingest',
  /** The meeting-text index's full-text search, answered with its provenance. */
  meetingSearch: '/meeting/search',
  /** Index one meeting container's records, read through the same gate. */
  meetingIngest: '/meeting/ingest',
  /** The six quality checks over one closed round's dossier manifest. */
  reviewQuality: '/review/quality',
  /** Ask the running apply round to stop at its next publication checkpoint. */
  reviewApplyCancel: '/review/apply/cancel',
  /** The rules a card may cite: mentor-confirmed, still standing, in scope. */
  guidanceUsable: '/guidance/usable',
  /** The pilot's issue record: what the trial met, as it was seen. */
  issues: '/issues',
  /** The four states one issue walks, from its record to its close. */
  issueStatus: '/issues/{issue_id}/status',
  /** One mentor's publication of a confirmed rule to the group. */
  guidanceRulePublish: '/guidance/rules/{rule_id}/publish',
  /** The retraction of one rule's sharing, leaving the rule standing. */
  guidanceRuleRetract: '/guidance/rules/{rule_id}/retract',
} as const

/** One review round's opinions, addressed by the round's two names. */
export function reviewOpinionsPath(projectId: string, versionId: string): string {
  const query = new URLSearchParams({ project_id: projectId, version_id: versionId })
  return `${API_PATHS.reviewOpinions}?${query.toString()}`
}

/** One review round's manuscript, addressed the same way its opinions are. */
export function reviewManuscriptPath(projectId: string, versionId: string): string {
  const query = new URLSearchParams({ project_id: projectId, version_id: versionId })
  return `${API_PATHS.reviewManuscript}?${query.toString()}`
}

/**
 * One closed binding's four deliverables, addressed by the dossier that binds
 * them.
 *
 * **The binding is named by its dossier, not remembered.** The apply's answer
 * carries the dossier's id, and the export is asked for by that id — so the
 * four files a panel draws are the four files *that round* bound, and not
 * whichever dossier happens to be the latest.
 */
export function reviewDeliverablesPath(projectId: string, dossierArtifactId: string): string {
  const query = new URLSearchParams({
    project_id: projectId,
    dossier_artifact_id: dossierArtifactId,
  })
  return `${API_PATHS.reviewDeliverables}?${query.toString()}`
}

/**
 * What the apply round is asked for, in the service's own words.
 *
 * The preview and the apply routes take **the same body**, because the
 * preview answers the apply's question about the same round — what these
 * addresses name. The fields are the service's (`ApplyReviewBody`, from the
 * generated types), so the client's spelling and the service's cannot drift:
 * a field renamed on one side fails the compile, not the round.
 */
export type ApplyReviewRequest = ApplyReviewBody

/** One review round's previews and writes, addressed by its two names. */
export function reviewApplyBody(
  projectId: string,
  inputVersionId: string,
  options: {
    readonly sourceRootId: string
    readonly sourceKey: string
    readonly outputLabel: string
    readonly windowEnd: string
  },
): ApplyReviewRequest {
  return {
    project_id: projectId,
    input_version_id: inputVersionId,
    source_root_id: options.sourceRootId,
    source_key: options.sourceKey,
    output_label: options.outputLabel,
    window_end: options.windowEnd,
  }
}

/**
 * The template of an artefact's bytes.
 *
 * The braces are the service's own parameter name, so that the drift check
 * can compare this with the route the service declares without either side
 * being rewritten to suit the other.
 */
export const ARTIFACT_CONTENT_PATH = '/artifacts/{artifact_id}/content'

/**
 * The template of one approval's grant.
 *
 * A change, so it needs the session token — which is why it is a POST and
 * why the client sends the token for it.
 */
export const APPROVAL_GRANT_PATH = '/approvals/{approval_id}/grant'

/**
 * The template of one proposal's acceptance.
 *
 * A change, so it needs the session token. The route settles the proposal by
 * the layer's own operation: the person's record is written, the proposal is
 * superseded and kept, and the service's answer is what the panel shows.
 */
export const PROPOSAL_ACCEPT_PATH = '/records/{evidence_id}/accept'

/**
 * The path of one artefact's bytes.
 *
 * The id is encoded, because a path segment that carries a slash would
 * address a different route — and an id that is not encoded is a path the
 * service reads as something else.
 */
export function artifactContentPath(receiptId: string): string {
  return ARTIFACT_CONTENT_PATH.replace('{artifact_id}', encodeURIComponent(receiptId))
}

/** The path of one approval's grant. */
export function approvalGrantPath(approvalId: string): string {
  return APPROVAL_GRANT_PATH.replace('{approval_id}', encodeURIComponent(approvalId))
}

/** The path of one proposal's acceptance. */
export function proposalAcceptPath(evidenceId: string): string {
  return PROPOSAL_ACCEPT_PATH.replace('{evidence_id}', encodeURIComponent(evidenceId))
}

/**
 * One event-stream request, resuming after *afterSeq*.
 *
 * **The cursor is the whole point.** A client that reconnects without one
 * either repeats events it already has or starts from zero and misses
 * nothing only by luck; the service's page carries `next_after_seq`, and
 * this is where the client says it. `poll_seconds` is the stream's own pace
 * and is left to the service's default when the caller does not say.
 */
export function eventsStreamPath(afterSeq: number, pollSeconds?: number): string {
  const query = [`after_seq=${afterSeq}`, 'follow=true']
  if (pollSeconds !== undefined) {
    query.push(`poll_seconds=${pollSeconds}`)
  }
  return `${API_PATHS.eventsStream}?${query.join('&')}`
}

/** Which task the service should be bound to. */
export function taskSelectBody(taskId: string): { task_id: string } {
  return { task_id: taskId }
}

/**
 * The template of one rule's verdict.
 *
 * A change, so it needs the session token — which is why it is a POST and
 * why the client sends the token for it. The id is encoded, for the same
 * reason the artefact's is: a path segment that carries a slash would
 * address a different rule.
 */
export const GUIDANCE_RULE_CONFIRM_PATH = '/guidance/rules/{rule_id}/confirm'

/** The path of one rule's verdict. */
export function guidanceRuleConfirmPath(ruleId: string): string {
  return GUIDANCE_RULE_CONFIRM_PATH.replace('{rule_id}', encodeURIComponent(ruleId))
}

/**
 * One issue's advisor trajectory.
 *
 * **The issue is a query parameter, and it is the caller's to name.** The
 * route takes the chain's own keys and the chain has no other outlet, so a
 * caller that has not named an issue has nothing to ask about. The key is
 * encoded, because a key that is not encoded is a key the service reads as
 * something else.
 */
export function trajectoryPath(issueKey: string): string {
  return `${API_PATHS.trajectory}?issue_key=${encodeURIComponent(issueKey)}`
}

/**
 * The project's versions, and the accepted edges between them.
 *
 * **The versions are named, and the naming is the caller's.** The route
 * answers with the versions the project holds *among the ones named*, so a
 * version nobody named is a version the answer does not carry — and the
 * panel that draws the graph says which versions it asked about.
 *
 * **The project is named too**, for the same reason: no route carries a
 * project id, so the caller supplies the one it means.
 */
export function trajectoryGraphPath(projectId: string, versionIds: readonly string[]): string {
  const query = [
    `project_id=${encodeURIComponent(projectId)}`,
    ...versionIds.map((versionId) => `version_id=${encodeURIComponent(versionId)}`),
  ].join('&')
  return `${API_PATHS.trajectoryGraph}?${query}`
}

/**
 * The chain's issue keys for a project: **what there is to look at**.
 *
 * **The project is named as a query parameter**, the way the graph's is —
 * the route answers about a project, and the project id is the caller's to
 * name. The keys are the chain's own, and they are names: the answer
 * carries no comment's words, so a panel that draws this draws names and
 * nothing else.
 */
export function issueKeysPath(projectId: string): string {
  return `${API_PATHS.issueKeys}?project_id=${encodeURIComponent(projectId)}`
}

/**
 * The query the three search routes share.
 *
 * **The question carries its own limit**, because a search over three
 * sources is three searches and the panel asks for a page's worth of each
 * rather than the whole index. The fields are the service's own query
 * parameters — `q`, `project_id`, `limit` — so the client's spelling and the
 * service's cannot drift without the route answering nothing.
 */
export interface SearchQuery {
  /** The words to look for. The route requires at least one character. */
  readonly q: string
  /** The paper project to search within, when the search is scoped. */
  readonly projectId?: string | undefined
  /** How many hits to ask for. The service caps this at 200. */
  readonly limit?: number | undefined
}

/** One search route's question, as the query string it is served with. */
function searchPath(path: string, query: SearchQuery): string {
  const params = new URLSearchParams({ q: query.q })
  if (query.projectId !== undefined && query.projectId !== '') {
    params.set('project_id', query.projectId)
  }
  if (query.limit !== undefined) {
    params.set('limit', String(query.limit))
  }
  return `${path}?${params.toString()}`
}

/** The advisor trajectory's search: what was said and changed, and where. */
export function trajectorySearchPath(query: SearchQuery): string {
  return searchPath(API_PATHS.trajectorySearch, query)
}

/** The slide deck index's search: what a slide or its notes say, and where. */
export function pptSearchPath(query: SearchQuery): string {
  return searchPath(API_PATHS.pptSearch, query)
}

/** The meeting-text index's search: what a record of a meeting says, and where. */
export function meetingSearchPath(query: SearchQuery): string {
  return searchPath(API_PATHS.meetingSearch, query)
}

/**
 * Where one ingest asks the service to read from.
 *
 * **The body names where to read; the bytes come from the workspace.** The
 * routes take no bytes — the deck or the meeting container is read through
 * the `source.read` gate from the root and resource key the caller names —
 * so the request is the three names and nothing more. The fields are the
 * service's own (`PptIngestBody` / `MeetingIngestBody`, from the generated
 * types), so a field renamed on one side fails the compile, not the ingest.
 */
export interface IngestRequest {
  /** The paper project the material is bound to. */
  readonly projectId: string
  /** The workspace root the material stands in. */
  readonly rootId: string
  /** The material's key inside its root. */
  readonly resourceKey: string
}

/** The slide-deck ingest's body, in the service's own field names. */
export function pptIngestBody(request: IngestRequest): PptIngestBody {
  return {
    project_id: request.projectId,
    root_id: request.rootId,
    resource_key: request.resourceKey,
  }
}

/** The meeting-text ingest's body, in the service's own field names. */
export function meetingIngestBody(request: IngestRequest): MeetingIngestBody {
  return {
    project_id: request.projectId,
    root_id: request.rootId,
    resource_key: request.resourceKey,
  }
}

/**
 * One closed round's six quality checks, addressed by its dossier.
 *
 * **The round is named by the dossier the apply answered with**, the same
 * name the deliverables are asked by — so the six checks measure the
 * manifest *that round* bound, and not whichever dossier is latest.
 */
export function reviewQualityPath(projectId: string, dossierArtifactId: string): string {
  const query = new URLSearchParams({
    project_id: projectId,
    dossier_artifact_id: dossierArtifactId,
  })
  return `${API_PATHS.reviewQuality}?${query.toString()}`
}

/**
 * The rules a card may cite.
 *
 * **The route serves confirmed rules only** — a candidate reaching a card
 * would be a proposal dressed as a record — and the scope is the caller's to
 * name, because the card that asks knows the narrowest scope it can live
 * with. The limit is the page size, and the service caps it at 200.
 */
export function guidanceUsablePath(scope?: string, limit?: number): string {
  const params = new URLSearchParams()
  if (scope !== undefined && scope !== '') {
    params.set('scope', scope)
  }
  if (limit !== undefined) {
    params.set('limit', String(limit))
  }
  const query = params.toString()
  return query === '' ? API_PATHS.guidanceUsable : `${API_PATHS.guidanceUsable}?${query}`
}

/**
 * The report render.
 *
 * A change, so it needs the session token: the service writes the report's four
 * forms into the task's own output area and records the revision. It is a POST
 * with a body rather than a read of an existing artefact because the plan's own
 * exit test says the **web produces** the same versioned report the CLI produces
 * — not that it displays one the CLI happened to write.
 *
 * The body carries the two claims the caller makes and the service takes no
 * default for either, so `reportRenderBody` is where this page states them.
 * `template_id` is `'default'` because exactly one template exists; asking for
 * another is a refusal that names it rather than a substitution.
 */
export const REPORT_RENDER_PATH = '/report'

/** What the workbench asks the service to render, and from which template. */
export function reportRenderBody(path = 'report', templateId = 'default'): Record<string, string> {
  return { path, template_id: templateId }
}

/**
 * The consent request, and the figure run it authorises.
 *
 * A figure needs **two** writes, not one: an approval that covers the material,
 * the operator, its parameters and the recipe's path (ADR-0012 constraint 7),
 * and the run that spends it. The service exposes both — `POST /approvals` asks
 * and `POST /analysis` runs — and this page calls them in that order. There is
 * deliberately no shortcut on this side either: a page that minted its own
 * consent would be the same bypass as a command that did.
 */
export const APPROVAL_REQUEST_PATH = '/approvals'
export const ANALYSIS_RUN_PATH = '/analysis'

/** The four fields the approval and the run must agree on, spelled once. */
export interface AnalysisArguments {
  readonly path: string
  readonly operatorId: string
  readonly recipe: string
  readonly parameters: Record<string, unknown>
}

/** The capability's arguments, in the one spelling the digest is taken over. */
interface AnalysisArgumentsBody {
  readonly path: string
  readonly operator_id: string
  readonly recipe: string
  readonly parameters: Record<string, unknown>
}

function analysisArguments(inputs: AnalysisArguments): AnalysisArgumentsBody {
  return {
    path: inputs.path,
    operator_id: inputs.operatorId,
    recipe: inputs.recipe,
    parameters: inputs.parameters,
  }
}

/**
 * What the workbench asks a human to consent to.
 *
 * `resource_key` is the material's key **inside its root**, because that is what
 * a policy rule is matched against and what the approval binds. `expires_at` is
 * passed in rather than read from the clock here, so the test can state the
 * moment and the page can choose its own window.
 */
export function analysisApprovalBody(inputs: {
  readonly rootId: string
  readonly expiresAt: string
  readonly arguments: AnalysisArguments
}): {
  capability: 'analysis.run'
  arguments: AnalysisArgumentsBody
  root_id: string
  resource_key: string
  depends_on: string[]
  expires_at: string
  stage_name: string
} {
  return {
    capability: 'analysis.run',
    arguments: analysisArguments(inputs.arguments),
    root_id: inputs.rootId,
    resource_key: inputs.arguments.path,
    depends_on: [],
    expires_at: inputs.expiresAt,
    stage_name: 'analysis',
  }
}

/** What the workbench asks the service to draw, under the approval it was given. */
export function analysisBody(
  inputs: { readonly rootId: string; readonly approvalId: string } & AnalysisArguments,
): {
  root_id: string
  path: string
  operator_id: string
  recipe: string
  parameters: Record<string, unknown>
  approval_id: string
} {
  return {
    root_id: inputs.rootId,
    ...analysisArguments(inputs),
    approval_id: inputs.approvalId,
  }
}

/**
 * The pilot's issues, narrowed by what is asked for.
 *
 * **The project is required, the service refuses a list without one** — an
 * issue is recorded about a project, so a listing without a project would be
 * a listing of nothing. The two filters are optional, and a filter narrows
 * rather than refuses: the service answers an empty list, not a 404.
 */
export function issuesPath(projectId: string, status?: string, severity?: string): string {
  const params = new URLSearchParams({ project_id: projectId })
  if (status !== undefined && status !== '') {
    params.set('status', status)
  }
  if (severity !== undefined && severity !== '') {
    params.set('severity', severity)
  }
  return `${API_PATHS.issues}?${params.toString()}`
}

/**
 * One issue's walk along its four states.
 *
 * **The id is encoded, because a path is not a place for a raw id.** The body
 * is the service's (`IssueStatusBody`, from the generated types), and the
 * project travels in it — the route refuses an issue that belongs to another
 * project rather than answering the move.
 */
export function issueStatusPath(issueId: string): string {
  return API_PATHS.issueStatus.replace('{issue_id}', encodeURIComponent(issueId))
}

/** One rule's publication to the group, at the path the service declares. */
export function guidanceRulePublishPath(ruleId: string): string {
  return API_PATHS.guidanceRulePublish.replace('{rule_id}', encodeURIComponent(ruleId))
}

/** The retraction of one rule's sharing, leaving the rule itself standing. */
export function guidanceRuleRetractPath(ruleId: string): string {
  return API_PATHS.guidanceRuleRetract.replace('{rule_id}', encodeURIComponent(ruleId))
}
