/**
 * The workbench: the task, drawn.
 *
 * **What state this holds.** Three things, and none of them is a decision
 * about the task: the API's last answer, the outcome of the last request the
 * page made, and whether a request is in flight. What is on the screen is
 * that answer, read again on every render — so what is on the screen is the
 * database's state, and a reload recovers that state rather than a copy of
 * it.
 *
 * **The one thing it changes.** Granting a pending approval. That is a
 * change, so the service wants the session token, and the token goes in a
 * header the client builds — this component never holds it and never shows
 * it. The button is disabled while a grant is in flight, because the plan's
 * rule is that the operation that follows is applied **once**: a double
 * click that sent two grants would be two operations, and one of them would
 * be a grant nobody asked for.
 *
 * **What it does not do.** It does not decide whether a report is ready, and
 * it does not draw the report's wording. The report says what it says; the
 * workbench shows the artefacts and their preview.
 */

import type { JSX } from 'react'
import { useCallback, useState } from 'react'

import { api, describeError } from '../api/client'
import type { ApprovalGranted, ReportRendered } from '../api/generated'
import { approvalGrantPath, REPORT_RENDER_PATH, reportRenderBody } from '../api/paths'
import { ApprovalView } from '../views/ApprovalView'
import { ArtefactsView } from '../views/ArtefactsView'
import { EvidenceView } from '../views/EvidenceView'
import { PlanView } from '../views/PlanView'
import { ProjectsView } from '../views/ProjectsView'
import { RevisionsView } from '../views/RevisionsView'
import { SourcesView } from '../views/SourcesView'
import { StepsView } from '../views/StepsView'
import { useWorkbench } from './useWorkbench'

/** What the last request did, and whether one is in flight. */
interface ActionState {
  /** Whether a grant is on its way to the service. */
  readonly granting: boolean
  /** Whether a report render is on its way to the service. */
  readonly rendering: boolean
  /** Why the last request was refused, when it was. */
  readonly refusal: string | null
}

const IDLE: ActionState = { granting: false, rendering: false, refusal: null }

export function Workbench(): JSX.Element {
  const { reads, readAgain } = useWorkbench(api)
  const [action, setAction] = useState<ActionState>(IDLE)

  const onGrant = useCallback(
    (approvalId: string) => {
      setAction({ ...IDLE, granting: true })
      void api.post<ApprovalGranted>(approvalGrantPath(approvalId)).then(
        () => {
          setAction(IDLE)
          // Read the task again rather than marking the approval granted
          // here: the service's record is the answer, and this page's guess
          // at it is not.
          readAgain()
        },
        (error: unknown) => {
          setAction({ ...IDLE, refusal: describeError(error).message })
        },
      )
    },
    [readAgain],
  )

  const onRenderReport = useCallback(() => {
    setAction({ ...IDLE, rendering: true })
    void api.post<ReportRendered>(REPORT_RENDER_PATH, reportRenderBody()).then(
      () => {
        setAction(IDLE)
        // The artefact list is the answer, not this page's memory of the
        // receipt the POST returned: the revision the service wrote is a
        // record, and the screen shows records.
        readAgain()
      },
      (error: unknown) => {
        // A refused report writes nothing, so the only thing worth showing is
        // the service's own reason — including the common one, that this task
        // holds no record a report may carry.
        setAction({ ...IDLE, refusal: describeError(error).message })
      },
    )
  }, [readAgain])

  const task = reads.state.data?.task ?? null

  return (
    <main className="workbench">
      <header className="workbench__header">
        <h1 className="workbench__title">{task?.title ?? 'LabCairn'}</h1>
        {task !== null ? (
          <p className="workbench__goal">
            {task.goal.objective}
            <span className="workbench__criterion">Success: {task.goal.success_criterion}</span>
          </p>
        ) : null}
        {reads.health.error !== null ? (
          <p className="workbench__banner" role="status">
            The local service did not answer: {reads.health.error.message}
          </p>
        ) : null}
        {action.refusal !== null ? (
          <p className="workbench__banner workbench__banner--refusal" role="status">
            The service refused that: {action.refusal}
          </p>
        ) : null}
      </header>

      <p className="workbench__actions">
        <button
          className="button"
          type="button"
          disabled={action.rendering}
          onClick={onRenderReport}
        >
          {action.rendering ? 'Rendering…' : 'Render the report'}
        </button>
      </p>

      <ProjectsView health={reads.health} tasks={reads.tasks} />
      <PlanView plan={reads.plan} />
      <StepsView steps={reads.steps} />
      <ApprovalView state={reads.state} onGrant={onGrant} granting={action.granting} />
      <SourcesView sources={reads.sources} />
      <EvidenceView plan={reads.plan} steps={reads.steps} />
      <ArtefactsView artifacts={reads.artifacts} />
      <RevisionsView artifacts={reads.artifacts} />

      <footer className="workbench__footer">
        <p>
          The session token is held in this page&rsquo;s memory and is presented as a header. It is
          not in the URL, not in the DOM and not in any log.
          {reads.session.data !== null ? ` The service wrote it to ${reads.session.data}.` : ''}
        </p>
        <p>
          This page talks to the local API and to nothing else. It loads no remote font, no remote
          script and no analytics.
        </p>
        <p>
          The service&rsquo;s event stream is not read here. This page shows the task&rsquo;s state
          and reads it again when something changes.
        </p>
      </footer>
    </main>
  )
}
