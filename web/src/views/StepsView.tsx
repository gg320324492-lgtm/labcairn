/**
 * The steps: the runtime stages the store holds.
 *
 * The steps are a **record**, not a declaration. Each one is a stage that
 * ran, in the run it belonged to, and the attempt that run made. A stage
 * that ran outside the declared workflow is still visible here, and a
 * declared stage nobody reached is still visible in the plan.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { TaskStep } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface StepsViewProps {
  /** The runtime stages the store holds, with the run each belonged to. */
  readonly steps: ApiRead<TaskStep[]>
}

export function StepsView({ steps }: StepsViewProps): JSX.Element {
  return (
    <Panel title="Steps" read={steps}>
      {(data) => (
        <>
          <p className="panel__note">
            What actually ran. Each step belongs to a run and to that run&rsquo;s attempt.
          </p>
          <RecordList>
            {data.map((step) => (
              <li
                className="record"
                key={step.stage.stage_id ?? `${step.stage.run_id}-${step.stage.name}`}
              >
                <span className="record__name">{step.stage.name}</span>
                <span className={`record__flag record__flag--${step.stage.status ?? 'unknown'}`}>
                  {step.stage.status ?? 'unknown'}
                </span>
                <span className="record__detail">attempt {step.attempt}</span>
                <span className="record__detail">run {step.stage.run_id}</span>
                {step.stage.blocked_reason !== undefined && step.stage.blocked_reason !== null ? (
                  <span className="record__detail">{step.stage.blocked_reason}</span>
                ) : null}
              </li>
            ))}
          </RecordList>
        </>
      )}
    </Panel>
  )
}
