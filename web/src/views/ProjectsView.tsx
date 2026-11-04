/**
 * Project selection: the tasks in this workspace, the one the service is
 * bound to, and the way to move the binding.
 *
 * **The service answers about one task at a time.** `GET /health` names it,
 * and the routes below it answer about that task and no other. Until the
 * selection route existed the workbench could only show that a workspace
 * held more than one task; now it offers the switch, and the switch is a
 * request rather than a page decision.
 *
 * **The page does not decide the selection.** Choosing a task POSTs to the
 * service, and the service's answer — the same `Health` every other read
 * sees — is what the page then reads. A view that marked a task selected
 * before the service agreed would be a second source of truth about which
 * task the work is about, which is the spelling this workbench exists to
 * avoid.
 *
 * **The switch is disabled while one is in flight**, for the same reason
 * every other button is: a second click would be a second selection, and the
 * two could land in either order.
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
  /** Ask the service to bind itself to another task. */
  readonly onSelect: (taskId: string) => void
  /** Whether a selection is on its way to the service. */
  readonly selecting: boolean
}

export function ProjectsView({
  health,
  tasks,
  onSelect,
  selecting,
}: ProjectsViewProps): JSX.Element {
  const bound = health.data?.task_id ?? null
  return (
    <Panel title="Projects" read={tasks}>
      {(data) => (
        <>
          {health.data !== null ? (
            <p className="panel__note">
              The service is listening on {health.data.host}:{health.data.port} and is bound to one
              task. Choosing another one moves the selection the CLI reads as well, so both surfaces
              stay about the same task. It answers to{' '}
              {health.data.origins.join(', ') || 'no other origin'}.
            </p>
          ) : null}
          <RecordList>
            {data.map((task) => {
              const taskId = task.task_id
              return (
                <li className="record" key={taskId ?? task.title}>
                  <span className="record__name">{task.title}</span>
                  {taskId !== undefined ? <span className="record__key">{taskId}</span> : null}
                  {taskId !== undefined && taskId === bound ? (
                    <span className="record__flag">selected</span>
                  ) : taskId !== undefined ? (
                    <button
                      className="button"
                      type="button"
                      disabled={selecting}
                      onClick={() => {
                        onSelect(taskId)
                      }}
                    >
                      Select
                    </button>
                  ) : null}
                  <span className="record__detail">{task.goal.objective}</span>
                  {task.revision !== undefined ? (
                    <span className="record__detail">revision {task.revision}</span>
                  ) : null}
                </li>
              )
            })}
          </RecordList>
        </>
      )}
    </Panel>
  )
}
