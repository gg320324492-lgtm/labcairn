/**
 * The plan: the declared workflow, and how far this task has got through it.
 *
 * The plan is a **declaration**, not a record. It says where the task
 * should be; the steps say what actually happened. Neither is derived from
 * the other, and this view draws only the declaration — the runtime record
 * is the steps' business.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { TaskPlan } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface PlanViewProps {
  /** The declared workflow and how far this task has got through it. */
  readonly plan: ApiRead<TaskPlan>
}

export function PlanView({ plan }: PlanViewProps): JSX.Element {
  return (
    <Panel title="Plan" read={plan}>
      {(data) => (
        <>
          <p className="panel__note">
            Declared by {data.skill_id} (digest {data.skill_digest}). A declaration, not a record:
            what actually ran is under Steps.
          </p>
          <RecordList>
            {data.steps.map((step) => (
              <li className="record" key={step.stage}>
                <span className="record__name">{step.stage}</span>
                <span className={`record__flag record__flag--${step.status}`}>{step.status}</span>
                {step.blocked_reason !== undefined && step.blocked_reason !== null ? (
                  <span className="record__detail">{step.blocked_reason}</span>
                ) : null}
              </li>
            ))}
          </RecordList>
        </>
      )}
    </Panel>
  )
}
