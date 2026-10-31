/**
 * The advisor's trajectory: what was written, what changed in answer, and how
 * the versions stand.
 *
 * **What the contract carries.** The route serves the chain's own facts —
 * `application.chain`'s comments, edits and response states — and the
 * project's versions with **only its accepted edges**. An edge nobody
 * accepted is a proposal, and a proposal may not decide an order, so the
 * graph this panel draws is the one the accepted edges describe.
 *
 * **The versions are a set, and this panel does not pretend otherwise.** The
 * layer answers with a `frozenset`, so the array the contract serialises has
 * **no stable order**: the same graph asked twice may arrive in two orders.
 * The panel therefore draws the versions as the set it is — sorted, and
 * numbered by nothing — and puts the only order the contract carries, the
 * edges', beside it. A panel that numbered the versions would be drawing a
 * chronology the contract does not carry, and a reader would believe it.
 *
 * **The panel cannot list what there is to look at.** No route serves the
 * chain's issue keys, and no route carries a project id, so the issue and
 * the project are the caller's to name — and **a panel that cannot list
 * what there is to look at has no way in**. The missing outlet is written
 * here rather than left for the next reader to find: an endpoint that lists
 * the chain's issues is what the workbench would need to open this panel,
 * and whether it is wanted is the owner's call, not this panel's.
 *
 * **What the panel does not draw.** The chain's rows carry no time, so the
 * panel shows no time and no order of the comments beyond the order the
 * service answered in. A version is an id and nothing else, so the panel
 * shows the id and no words of the paper. The route serves only accepted
 * edges, so there is no proposed edge to draw and none is invented.
 */

import { useId, useState } from 'react'
import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { ChainEdit, ProjectGraph, Trajectory } from '../api/generated'
import { trajectoryGraphPath, trajectoryPath } from '../api/paths'
import { Panel, RecordList } from './Panel'
import { usePanelRead } from './usePanelRead'

/** What the trajectory panel draws: the answer, or the panel's own state. */
type TrajectoryAnswer =
  { readonly asked: false } | { readonly asked: true; readonly trajectory: Trajectory }

/** What the version panel draws: the answer, or the panel's own state. */
type GraphAnswer =
  | { readonly asked: false; readonly why: string }
  | {
      readonly asked: true
      readonly graph: ProjectGraph
      /** The versions the panel asked about, so the reader can see what it named. */
      readonly versions: readonly string[]
    }

/** What the panel is asked about. */
interface Question {
  /** The chain's key for the issue, as the caller named it. */
  readonly issue: string
  /** The paper project, as the caller named it. */
  readonly project: string
}

/**
 * The versions the comments name, without repeats and in a stable order.
 *
 * **The order is the query's, not the chain's.** The comments arrive in the
 * service's order, which the contract does not promise, so the versions are
 * sorted before they are named in the query: the same chain asked twice asks
 * the same question.
 */
function versionIdsOf(trajectory: Trajectory | null): string[] {
  if (trajectory === null) {
    return []
  }
  const named = new Set<string>()
  for (const comment of trajectory.comments) {
    named.add(comment.version_id)
  }
  return [...named].sort()
}

/** The edits that answer the comment named, and the ones that answer none. */
function editsFor(trajectory: Trajectory): {
  answered: Map<string, ChainEdit[]>
  loose: ChainEdit[]
} {
  const answered = new Map<string, ChainEdit[]>()
  const loose: ChainEdit[] = []
  for (const edit of trajectory.edits) {
    if (edit.feedback_id === null) {
      loose.push(edit)
      continue
    }
    const group = answered.get(edit.feedback_id)
    if (group === undefined) {
      answered.set(edit.feedback_id, [edit])
    } else {
      group.push(edit)
    }
  }
  return { answered, loose }
}

/** The states the answer ties to the comment named. */
function statesFor(trajectory: Trajectory, feedbackId: string): string[] {
  const response = trajectory.responses.find((entry) => entry.feedback_id === feedbackId)
  return response === undefined ? [] : response.states
}

/** One change, as the chain holds it. */
function EditRow({ edit }: { readonly edit: ChainEdit }): JSX.Element {
  return (
    <li className="record">
      <span className="record__name">{edit.actor_kind}</span>
      <span className="record__detail">grade {edit.grade}</span>
      <span className="record__detail">edge {edit.version_edge_id}</span>
      <span className="record__detail">edit {edit.edit_action_id}</span>
    </li>
  )
}

export function TrajectoryView(): JSX.Element {
  const [issueKey, setIssueKey] = useState('')
  const [projectId, setProjectId] = useState('')
  const [question, setQuestion] = useState<Question | null>(null)
  const headingId = useId()
  const field = (name: string): string => `${headingId}-${name}`

  const trajectory = usePanelRead<Trajectory>(
    question === null || question.issue === '' ? null : trajectoryPath(question.issue),
  )
  const versions = versionIdsOf(trajectory.read.kind === 'answered' ? trajectory.read.data : null)
  const graph = usePanelRead<ProjectGraph>(
    question === null || question.project === '' || versions.length === 0
      ? null
      : trajectoryGraphPath(question.project, versions),
  )

  const trajectoryAnswer: TrajectoryAnswer | null =
    trajectory.read.kind === 'idle'
      ? { asked: false }
      : trajectory.read.kind === 'answered'
        ? { asked: true, trajectory: trajectory.read.data }
        : null
  const trajectoryPanel: ApiRead<TrajectoryAnswer> =
    trajectory.read.kind === 'failed'
      ? { data: null, error: trajectory.read.error }
      : { data: trajectoryAnswer, error: null }

  const graphAnswer: GraphAnswer | null =
    graph.read.kind === 'idle'
      ? {
          asked: false,
          why:
            question === null
              ? 'Nothing has been asked for yet.'
              : question.project === ''
                ? 'No project is named, so no versions are drawn.'
                : 'The comments name no version, so the project was not asked about.',
        }
      : graph.read.kind === 'answered'
        ? { asked: true, graph: graph.read.data, versions }
        : null
  const graphPanel: ApiRead<GraphAnswer> =
    graph.read.kind === 'failed'
      ? { data: null, error: graph.read.error }
      : { data: graphAnswer, error: null }

  const ask = (): void => {
    setQuestion({ issue: issueKey.trim(), project: projectId.trim() })
  }

  return (
    <>
      <Panel title="Trajectory" read={trajectoryPanel}>
        {(answer) => (
          <>
            <p className="panel__note">
              The advisor&rsquo;s comments, the edits that answered them, and the states of the
              responses. The service has no outlet that lists the chain&rsquo;s issue keys, so this
              panel cannot list what there is to look at: name an issue below.
            </p>
            <div className="figure-form">
              <label htmlFor={field('issueKey')}>
                Issue key
                <input
                  id={field('issueKey')}
                  value={issueKey}
                  onChange={(event) => {
                    setIssueKey(event.target.value)
                  }}
                />
              </label>
              <label htmlFor={field('projectId')}>
                Project id
                <input
                  id={field('projectId')}
                  value={projectId}
                  onChange={(event) => {
                    setProjectId(event.target.value)
                  }}
                />
              </label>
            </div>
            <p className="panel__actions">
              <button className="button" type="button" onClick={ask}>
                Draw the trajectory
              </button>
            </p>
            {answer.asked ? (
              <TrajectoryBody trajectory={answer.trajectory} />
            ) : (
              <p className="panel__status">No issue has been named, so nothing has been asked.</p>
            )}
          </>
        )}
      </Panel>
      <Panel title="Version graph" read={graphPanel}>
        {(answer) => (
          <>
            <p className="panel__note">
              The project&rsquo;s versions and the accepted edges between them. The contract carries
              the versions as a set, so the order below is the display&rsquo;s and not the
              project&rsquo;s: the only order in the contract is the edges&rsquo;.
            </p>
            {answer.asked ? (
              <GraphBody graph={answer.graph} versions={answer.versions} />
            ) : (
              <p className="panel__status">{answer.why}</p>
            )}
          </>
        )}
      </Panel>
    </>
  )
}

/** The comments, the edits that answered them, and the states. */
function TrajectoryBody({ trajectory }: { readonly trajectory: Trajectory }): JSX.Element {
  const { answered, loose } = editsFor(trajectory)
  return (
    <>
      <h3 className="panel__subtitle">Comments</h3>
      {trajectory.comments.length === 0 ? (
        <p className="panel__status">The chain holds no comment under the issue named.</p>
      ) : (
        <RecordList>
          {trajectory.comments.map((comment) => {
            const edits = answered.get(comment.feedback_id) ?? []
            const states = statesFor(trajectory, comment.feedback_id)
            return (
              <li className="record record--artefact" key={comment.feedback_id}>
                <span className="record__name">{comment.comment_text}</span>
                <span className="record__detail">comment {comment.feedback_id}</span>
                <span className="record__detail">issue {comment.issue_key}</span>
                <span className="record__detail">version {comment.version_id}</span>
                <span className="record__detail">anchor: {comment.anchor_text}</span>
                <span className="record__detail">
                  states: {states.length === 0 ? 'none recorded' : states.join(', ')}
                </span>
                {edits.length === 0 ? (
                  <span className="record__detail">no edit answers this comment</span>
                ) : (
                  <RecordList>
                    {edits.map((edit) => (
                      <EditRow edit={edit} key={edit.edit_action_id} />
                    ))}
                  </RecordList>
                )}
              </li>
            )
          })}
        </RecordList>
      )}
      {loose.length > 0 ? (
        <>
          <h3 className="panel__subtitle">Changes the answer ties to no comment</h3>
          <RecordList>
            {loose.map((edit) => (
              <EditRow edit={edit} key={edit.edit_action_id} />
            ))}
          </RecordList>
        </>
      ) : null}
    </>
  )
}

/** The versions, and the accepted edges between them. */
function GraphBody({
  graph,
  versions,
}: {
  readonly graph: ProjectGraph
  readonly versions: readonly string[]
}): JSX.Element {
  const held = [...graph.version_ids].sort()
  const edges = [...graph.edges].sort((left, right) => left.edge_id.localeCompare(right.edge_id))
  return (
    <>
      <p className="panel__status">Asked about {versions.join(', ')}.</p>
      <h3 className="panel__subtitle">Versions</h3>
      {held.length === 0 ? (
        <p className="panel__status">The project holds none of the versions named.</p>
      ) : (
        <RecordList>
          {held.map((versionId) => (
            <li className="record" key={versionId}>
              <span className="record__name">version {versionId}</span>
            </li>
          ))}
        </RecordList>
      )}
      <h3 className="panel__subtitle">Accepted edges</h3>
      {edges.length === 0 ? (
        <p className="panel__status">No accepted edge joins the versions named.</p>
      ) : (
        <RecordList>
          {edges.map((edge) => (
            <li className="record" key={edge.edge_id}>
              <span className="record__name">
                {`${edge.parent_version_id} \u2192 ${edge.child_version_id}`}
              </span>
              <span className="record__detail">edge {edge.edge_id}</span>
            </li>
          ))}
        </RecordList>
      )}
    </>
  )
}
