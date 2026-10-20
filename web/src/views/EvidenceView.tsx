/**
 * The evidence status: where the task is in its evidence work.
 *
 * **What the contract can say about evidence.** The service's routes answer
 * about the task, its plan, its runtime stages, its material and its
 * artefacts. They do not carry the evidence records themselves — the
 * contract has no evidence route — so this view does not draw any. What it
 * draws is the two things the contract *does* say about evidence: how far
 * the **declared** workflow has got through its evidence stage, and what the
 * **runtime** stages named `evidence` recorded when they ran.
 *
 * That is a status and not a set of records, and the panel says so in as
 * many words rather than implying that the evidence itself is on the screen.
 * A panel that drew a list of claims it could not see would be a second
 * spelling of the evidence model, and a reader would believe it.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import { combineReads } from '../app/useWorkbench'
import type { TaskPlan, TaskStep } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface EvidenceViewProps {
  /** The declared workflow and how far this task has got through it. */
  readonly plan: ApiRead<TaskPlan>
  /** The runtime stages the store holds. */
  readonly steps: ApiRead<TaskStep[]>
}

/** The name the declared workflow gives the evidence stage. */
const EVIDENCE_STAGE = 'evidence'

export function EvidenceView({ plan, steps }: EvidenceViewProps): JSX.Element {
  const both = combineReads(plan, steps)
  return (
    <Panel title="Evidence" read={both}>
      {([declared, runtime]) => {
        const stage = declared.steps.find((entry) => entry.stage === EVIDENCE_STAGE) ?? null
        const ran = runtime.filter((step) => step.stage.name === EVIDENCE_STAGE)
        return (
          <>
            <p className="panel__note">
              The status of the task&rsquo;s evidence work. The service exposes no evidence records,
              so this is the stage&rsquo;s standing and nothing more.
            </p>
            {stage !== null ? (
              <p className="panel__status">
                Declared stage <strong>{stage.stage}</strong> is{' '}
                <strong className={`record__flag record__flag--${stage.status}`}>
                  {stage.status}
                </strong>
                {stage.blocked_reason !== undefined && stage.blocked_reason !== null
                  ? ` — ${stage.blocked_reason}`
                  : ''}
              </p>
            ) : (
              <p className="panel__status">The declared workflow has no evidence stage.</p>
            )}
            {ran.length > 0 ? (
              <>
                <h3 className="panel__subtitle">Runtime stages named evidence</h3>
                <RecordList>
                  {ran.map((step) => (
                    <li className="record" key={step.stage.stage_id ?? step.stage.run_id}>
                      <span className="record__name">{step.stage.name}</span>
                      <span
                        className={`record__flag record__flag--${step.stage.status ?? 'unknown'}`}
                      >
                        {step.stage.status ?? 'unknown'}
                      </span>
                      <span className="record__detail">attempt {step.attempt}</span>
                      {step.stage.blocked_reason !== undefined &&
                      step.stage.blocked_reason !== null ? (
                        <span className="record__detail">{step.stage.blocked_reason}</span>
                      ) : null}
                    </li>
                  ))}
                </RecordList>
              </>
            ) : null}
          </>
        )
      }}
    </Panel>
  )
}
