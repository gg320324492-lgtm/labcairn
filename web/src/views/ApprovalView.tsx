/**
 * The pending approval: the question the task is waiting on a human to
 * answer.
 *
 * **The grant is the one thing this workbench changes.** Everything else it
 * does is read. The grant needs the session token, because the service
 * requires it on every request that changes something, and the token goes
 * in the `Authorization` header and nowhere else — the client does that,
 * and this view never sees the token.
 *
 * **The view does not decide the outcome.** The button asks the service to
 * record the human's answer; the service records it and the workbench reads
 * the result back. A view that marked the approval granted the moment the
 * button was pressed would be showing the page's opinion rather than the
 * database's state, and a refused grant would then be a screen that says
 * "granted" over a task that never was.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { Approval, TaskState } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface ApprovalViewProps {
  /** The task state, which carries the approvals. */
  readonly state: ApiRead<TaskState>
  /** Ask the service to record the human's answer. */
  readonly onGrant: (approvalId: string) => void
  /** Whether a grant is in flight. */
  readonly granting: boolean
}

/** The approval that is waiting on an answer. */
function isPending(approval: Approval): boolean {
  return approval.state === 'pending'
}

export function ApprovalView({ state, onGrant, granting }: ApprovalViewProps): JSX.Element {
  return (
    <Panel title="Approval" read={state}>
      {(data) => {
        const pending = data.approvals.filter(isPending)
        const settled = data.approvals.filter((approval) => !isPending(approval))
        return (
          <>
            {pending.length === 0 ? (
              <p className="panel__note">Nothing is waiting on an answer.</p>
            ) : (
              <RecordList>
                {pending.map((approval) => (
                  <li className="record" key={approval.approval_id ?? approval.args_digest}>
                    <span className="record__name">{approval.capability}</span>
                    <span className="record__detail">{approval.resource_key}</span>
                    <span className="record__detail">arguments digest {approval.args_digest}</span>
                    <span className="record__detail">expires {approval.expires_at}</span>
                    {approval.approval_id !== undefined ? (
                      <button
                        className="button"
                        type="button"
                        disabled={granting}
                        onClick={() => {
                          onGrant(approval.approval_id ?? '')
                        }}
                      >
                        Grant
                      </button>
                    ) : null}
                  </li>
                ))}
              </RecordList>
            )}
            {settled.length > 0 ? (
              <>
                <h3 className="panel__subtitle">Already answered</h3>
                <RecordList>
                  {settled.map((approval) => (
                    <li className="record" key={approval.approval_id ?? approval.args_digest}>
                      <span className="record__name">{approval.capability}</span>
                      <span className={`record__flag record__flag--${approval.state ?? 'unknown'}`}>
                        {approval.state ?? 'unknown'}
                      </span>
                      <span className="record__detail">{approval.resource_key}</span>
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
