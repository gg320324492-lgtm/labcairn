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
