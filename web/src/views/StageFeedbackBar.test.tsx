import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { PlanStage, Stage, StageStatus, TaskPlan, TaskState } from '../api/generated'
import { StageFeedbackBar } from './StageFeedbackBar'
import { currentPhase, phaseSegments } from './stageFeedback'

/**
 * The stage feedback bar, read off the service's own answers.
 *
 * **What is checked here is that the bar does not invent state.** The phases
 * it draws come from the plan's declared stages and the task's runtime
 * statuses; a plan the service has not answered leaves the bar without a
 * claim; and every state is said twice — in text and in structure — so a
 * reader who cannot see the animation still knows where the work stands.
 */

const TASK_ID = '0193f0a1-0000-7000-8000-00000000b001'

const PLAN: TaskPlan = {
  task_id: TASK_ID,
  skill_id: 'paper-revision',
  skill_digest: 'c'.repeat(64),
  steps: [
    { stage: 'intake', status: 'completed' },
    { stage: 'inventory', status: 'completed' },
    { stage: 'retrieve', status: 'completed' },
    { stage: 'evidence', status: 'entered' },
    { stage: 'propose', status: 'pending' },
    { stage: 'draft', status: 'pending' },
    { stage: 'validate', status: 'pending' },
    { stage: 'deliver', status: 'pending' },
  ] as PlanStage[],
}

function runtimeStage(name: string, status: StageStatus): Stage {
  return {
    stage_id: `stage-${name}`,
    task_id: TASK_ID,
    run_id: 'run-1',
    name,
    status,
  }
}

const STATE: TaskState = {
  task: {
    task_id: TASK_ID,
    title: 'A revision round',
    goal: { objective: 'Revise the paper', success_criterion: 'All opinions answered' },
  },
  runs: [],
  stages: [runtimeStage('evidence', 'entered')],
  artifacts: [],
  approvals: [],
  last_event_seq: 4,
}

describe('the workbench phases', () => {
  it('read the plan’s declared stages and the runtime statuses', () => {
    const segments = phaseSegments(PLAN, STATE)

    expect(segments.map((segment) => segment.phase)).toEqual([
      'import',
      'locate',
      'suggest',
      'review',
      'apply',
      'deliver',
    ])
    expect(segments[0]).toMatchObject({ status: 'completed', stageNames: ['intake', 'inventory'] })
    expect(segments[1]).toMatchObject({ status: 'active', stageNames: ['retrieve', 'evidence'] })
    expect(segments[2]).toMatchObject({ status: 'pending', stageNames: ['propose'] })
    // The workbench's apply phase has no declared stage yet — it is the
    // delivery centre's own act — and it says so rather than borrowing one.
    expect(segments[4]).toMatchObject({ status: 'pending', stageNames: [] })

    // The plan's steps carry the service's own derivation of status; the bar
    // reads that, so a runtime stage that is absent still lands as declared.
    const planOnly = phaseSegments(PLAN, null)
    expect(planOnly[0]?.status).toBe('completed')
    expect(planOnly[1]?.status).toBe('active')
  })

  it('name the current phase: the first active one, else the furthest finished one', () => {
    expect(currentPhase(phaseSegments(PLAN, STATE))).toBe('locate')

    // A round at rest is at its last finished phase, not a decorated "active".
    const finished: TaskState = {
      ...STATE,
      stages: [
        runtimeStage('intake', 'completed'),
        runtimeStage('inventory', 'completed'),
        runtimeStage('retrieve', 'completed'),
        runtimeStage('evidence', 'completed'),
        runtimeStage('propose', 'completed'),
        runtimeStage('draft', 'completed'),
        runtimeStage('validate', 'completed'),
        runtimeStage('deliver', 'completed'),
      ],
    }
    expect(currentPhase(phaseSegments(PLAN, finished))).toBe('deliver')
  })
})

describe('the stage feedback bar', () => {
  it('says the current phase in text and marks it in structure', () => {
    render(<StageFeedbackBar plan={PLAN} state={STATE} />)

    const bar = screen.getByRole('group', { name: 'Workbench stage feedback' })
    expect(bar.getAttribute('data-stage')).toBe('locate')

    const status = screen.getByRole('status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status).toHaveTextContent('Current phase: Locate (in progress)')

    // The active phase carries the mapping in structure too: the bar segment
    // is named, and it is the one the screen is on.
    const activeSegment = document.querySelector('.stage-bar__phase[data-stage="locate"]')
    expect(activeSegment).not.toBeNull()
    expect(activeSegment?.getAttribute('data-status')).toBe('active')
  })

  it('draws every phase with its own text label and status word', () => {
    render(<StageFeedbackBar plan={PLAN} state={STATE} />)

    for (const label of ['Import', 'Locate', 'Suggest', 'Review', 'Apply', 'Deliver']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    // The fixture's round: import has finished, locate is running, and the
    // four phases behind it are still waiting.
    expect(screen.getAllByText('done')).toHaveLength(1)
    expect(screen.getAllByText('in progress')).toHaveLength(1)
    expect(screen.getAllByText('waiting')).toHaveLength(4)
  })

  it('claims no phase when the service has not answered with a plan', () => {
    render(<StageFeedbackBar plan={null} state={null} />)

    const bar = screen.getByText(/no phase is claimed yet/).closest('div')
    expect(bar?.getAttribute('data-stage')).toBe('none')
  })

  it('draws the runtime stages the store holds, even before a plan lands', () => {
    render(<StageFeedbackBar plan={null} state={STATE} />)

    expect(screen.getByText('Current phase: Locate (in progress)')).toBeInTheDocument()
    expect(screen.getByText('evidence')).toBeInTheDocument()
  })
})
