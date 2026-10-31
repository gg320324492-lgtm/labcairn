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
 * **The event stream is not among them.** The service offers `/events` and
 * `/events/stream`, and the workbench reads neither. The workbench shows the
 * task's state and reads it again when something changes; a long-lived
 * stream would be a second way to watch the task move, and the workbench's
 * rule is that the screen shows what the API says rather than what the page
 * has been told. The omission is a decision, and it is named here because a
 * missing path in this list is exactly where a reader would look for a
 * forgotten one.
 */

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
  /** The ledger's records for this task, each saying whose words it is. */
  records: '/records',
  /** The guidance rules the memory holds, each with its counterexamples. */
  guidanceRules: '/guidance/rules',
  /** One issue's advisor trajectory: the comments, the edits and the states. */
  trajectory: '/trajectory',
  /** A paper project's versions and the accepted edges between them. */
  trajectoryGraph: '/trajectory/graph',
} as const

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
