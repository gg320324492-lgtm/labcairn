/**
 * The stage feedback bar: the workbench's phases, drawn as they truly are.
 *
 * **The bar draws the service's plan, and nothing else.** The stages it shows
 * are the declared workflow's own — `GET /plan`'s steps, in the order the
 * service declared them, with each one's status read from the same answer.
 * A stage the service has not declared is not invented here, and a status the
 * service has not written is not decorated: the bar is a reading of state,
 * and a bar that moved on its own would be an animation pretending to be
 * information.
 *
 * **The workbench's phases and the plan's stages are not the same words.**
 * The product's phases — import, locate, suggest, review, apply, deliver —
 * are what a reader of the workbench follows; the plan's stages are what the
 * service runs. The mapping lives in `stageFeedback.ts`, and the bar says
 * it: every bar segment carries its `data-stage` phase, and the live region
 * names the phase and its evidence. What a reader cannot do is mistake the
 * bar's motion for a change the service never made.
 *
 * **Every state is said twice: in text and in structure.** The current phase
 * is announced in an `aria-live` region and marked with `data-stage` on the
 * bar; a phase is never communicated by colour or motion alone, so a reader
 * who cannot see the animation still knows where the work stands. The
 * transition itself is CSS, and it stands down under
 * `prefers-reduced-motion: reduce` — the motion is the decoration; the text
 * and the attributes are the information.
 */

import { useMemo } from 'react'
import type { JSX } from 'react'

import type { TaskPlan, TaskState } from '../api/generated'
import { currentPhase, phaseSegments } from './stageFeedback'
import type { PhaseStatus, WorkbenchPhase } from './stageFeedback'

/** What one phase is called on the bar. */
const PHASE_LABELS: Readonly<Record<WorkbenchPhase, string>> = {
  import: 'Import',
  locate: 'Locate',
  suggest: 'Suggest',
  review: 'Review',
  apply: 'Apply',
  deliver: 'Deliver',
}

/** How a status is said, in text a reader can act on. */
const STATUS_LABELS: Readonly<Record<PhaseStatus, string>> = {
  pending: 'waiting',
  active: 'in progress',
  completed: 'done',
}

/**
 * The stage feedback bar, drawn from the service's own plan and task state.
 *
 * Both reads arrive as the workbench's `ApiRead`: a read that has not landed
 * or failed leaves the bar without a claim to make, and the bar says that —
 * it does not draw a phase the service has not answered with.
 */
export function StageFeedbackBar({
  plan,
  state,
}: {
  readonly plan: TaskPlan | null
  readonly state: TaskState | null
}): JSX.Element {
  const segments = useMemo(() => phaseSegments(plan, state), [plan, state])
  const active = currentPhase(segments)
  const hasPlan = plan !== null || (state?.stages.length ?? 0) > 0

  if (!hasPlan) {
    return (
      <div className="stage-bar stage-bar--empty" data-stage={active ?? 'none'}>
        <p className="stage-bar__status" role="status">
          Stage feedback waits for the service&rsquo;s plan — no phase is claimed yet.
        </p>
      </div>
    )
  }

  return (
    <div
      className="stage-bar"
      role="group"
      aria-label="Workbench stage feedback"
      data-stage={active ?? 'none'}
    >
      <p
        className="stage-bar__status"
        role="status"
        aria-live="polite"
        data-stage={active ?? 'none'}
      >
        {active === null
          ? 'No phase is active yet — the service has not started a stage.'
          : `Current phase: ${PHASE_LABELS[active]} (${
              STATUS_LABELS[segments.find((s) => s.phase === active)?.status ?? 'pending']
            })`}
      </p>
      <ol className="stage-bar__phases">
        {segments.map((segment) => (
          <li
            key={segment.phase}
            className={`stage-bar__phase stage-bar__phase--${segment.status}`}
            data-stage={segment.phase}
            data-status={segment.status}
            aria-current={segment.phase === active ? 'step' : undefined}
          >
            <span className="stage-bar__phase-label">{PHASE_LABELS[segment.phase]}</span>
            <span className="stage-bar__phase-status">{STATUS_LABELS[segment.status]}</span>
            {segment.stageNames.length > 0 ? (
              <span className="stage-bar__phase-stages">
                {segment.stageNames.map((name) => (
                  <code key={name}>{name}</code>
                ))}
              </span>
            ) : (
              <span className="stage-bar__phase-stages stage-bar__phase-stages--absent">
                no declared stage
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
