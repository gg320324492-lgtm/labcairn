/**
 * Project selection: the tasks in this workspace, and the one the service is
 * bound to.
 *
 * **The service is bound to one task.** `GET /health` names it, and the
 * routes below it answer about that task and no other. So this view does not
 * offer a switch — it shows which project is selected and what else is in
 * the store, because a workspace holds more than one task and a reader who
 * saw only the bound one would not know that.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { Health, Task } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface ProjectsViewProps {
  /** What the service is, and where it listens. */
  readonly health: ApiRead<Health>
  /** Every task in this workspace's store. */
  readonly tasks: ApiRead<Task[]>
}

export function ProjectsView({ health, tasks }: ProjectsViewProps): JSX.Element {
  const bound = health.data?.task_id ?? null
  return (
    <Panel title="Projects" read={tasks}>
      {(data) => (
        <>
          {health.data !== null ? (
            <p className="panel__note">
              The service is listening on {health.data.host}:{health.data.port} and is bound to one
              task. It answers to {health.data.origins.join(', ') || 'no other origin'}.
            </p>
          ) : null}
          <RecordList>
            {data.map((task) => (
              <li className="record" key={task.task_id ?? task.title}>
                <span className="record__name">{task.title}</span>
                {task.task_id !== undefined ? (
                  <span className="record__key">{task.task_id}</span>
                ) : null}
                {task.task_id !== undefined && task.task_id === bound ? (
                  <span className="record__flag">selected</span>
                ) : null}
                <span className="record__detail">{task.goal.objective}</span>
                {task.revision !== undefined ? (
                  <span className="record__detail">revision {task.revision}</span>
                ) : null}
              </li>
            ))}
          </RecordList>
        </>
      )}
    </Panel>
  )
}
