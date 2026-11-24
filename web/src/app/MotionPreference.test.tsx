import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { PlanStage, Stage, StageStatus, TaskPlan, TaskState } from '../api/generated'
import { StageFeedbackBar } from '../views/StageFeedbackBar'
import { MotionPreference } from './MotionPreference'
import { MOTION_ATTRIBUTE, MOTION_STORAGE_KEY, REDUCED_MOTION_QUERY } from './motionState'

/**
 * The motion preference, on the screen.
 *
 * **What is checked here is that the control does what it says and says what
 * it does.** The default follows the system; the reader's choice stands the
 * motion down and survives a reload; a browser that refuses to store the
 * choice is told so rather than left to discover it at the next reload; and
 * the information the motion decorated is still there once the motion is
 * reduced — because the motion was never the information.
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

/** What a stubbed `matchMedia` can be asked to do. */
interface MediaStub {
  /** What the query answers from now on, and tells its listeners about. */
  set(matches: boolean): void
  /** Put the browser's own `matchMedia` back. */
  restore(): void
}

/**
 * A `matchMedia` that answers what the test tells it to answer.
 *
 * **The system is the other half of the decision,** so a test that says
 * nothing about the system is only testing half of it. The stub replaces the
 * browser's own `matchMedia` — the reader's system — with one this test
 * drives.
 */
function stubMatchMedia(initial: boolean): MediaStub {
  const listeners = new Set<EventListener>()
  let current = initial
  const list = {
    get matches(): boolean {
      return current
    },
    media: REDUCED_MOTION_QUERY,
    onchange: null,
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject): void => {
      if (typeof listener === 'function') {
        listeners.add(listener)
      }
    },
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject): void => {
      if (typeof listener === 'function') {
        listeners.delete(listener)
      }
    },
    addListener: (): void => {},
    removeListener: (): void => {},
    dispatchEvent: (): boolean => false,
  } as unknown as MediaQueryList

  // The DOM this test runs in has no `matchMedia` of its own — jsdom does
  // not implement one — so the browser's own is often nothing to put back.
  const original =
    typeof window.matchMedia === 'function' ? window.matchMedia.bind(window) : undefined
  window.matchMedia = (): MediaQueryList => list

  return {
    set(matches: boolean): void {
      current = matches
      for (const listener of [...listeners]) {
        listener({ matches } as MediaQueryListEvent)
      }
    },
    restore(): void {
      if (original === undefined) {
        delete (window as { matchMedia?: typeof window.matchMedia }).matchMedia
      } else {
        window.matchMedia = original
      }
    },
  }
}

/** The sentence the control states the motion in. */
function saidState(): string {
  return screen.getByRole('status').textContent ?? ''
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute(MOTION_ATTRIBUTE)
})

describe('the motion preference', () => {
  it('is offered, and says in words what the page is doing', () => {
    const media = stubMatchMedia(false)
    try {
      render(<MotionPreference />)

      expect(screen.getByLabelText('Motion')).toHaveValue('system')
      expect(saidState()).toContain('Motion is on')
    } finally {
      media.restore()
    }
  })

  it('follows the system when the reader has chosen nothing', () => {
    const media = stubMatchMedia(true)
    try {
      render(<MotionPreference />)

      // The control still offers the system's own choice, because that is
      // what it follows; the sentence says the motion is reduced, and the
      // root says so for the stylesheet.
      expect(screen.getByLabelText('Motion')).toHaveValue('system')
      expect(saidState()).toContain('Motion is reduced')
      expect(saidState()).toContain('the system asks for less')
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')
    } finally {
      media.restore()
    }
  })

  it('stands the motion down when the reader asks for it', () => {
    const media = stubMatchMedia(false)
    try {
      render(<MotionPreference />)

      fireEvent.change(screen.getByLabelText('Motion'), { target: { value: 'reduced' } })

      expect(saidState()).toContain('Motion is reduced')
      expect(saidState()).toContain('you asked this page')
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')
      expect(localStorage.getItem(MOTION_STORAGE_KEY)).toBe('reduced')
    } finally {
      media.restore()
    }
  })

  it('remembers the choice across a reload', () => {
    const media = stubMatchMedia(false)
    try {
      const first = render(<MotionPreference />)
      fireEvent.change(screen.getByLabelText('Motion'), { target: { value: 'reduced' } })
      first.unmount()

      render(<MotionPreference />)

      expect(screen.getByLabelText('Motion')).toHaveValue('reduced')
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')
    } finally {
      media.restore()
    }
  })

  it('says so when the browser refuses to remember the choice', () => {
    const media = stubMatchMedia(false)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('this browser refuses to store anything')
    })
    try {
      render(<MotionPreference />)

      fireEvent.change(screen.getByLabelText('Motion'), { target: { value: 'reduced' } })

      // The choice still holds for this page; what it did not do is survive.
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')
      expect(screen.getByText(/refused to remember/)).toBeInTheDocument()
    } finally {
      media.restore()
    }
  })

  it('follows the system while the page is open', () => {
    const media = stubMatchMedia(false)
    try {
      render(<MotionPreference />)
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('full')

      act(() => {
        media.set(true)
      })

      expect(saidState()).toContain('Motion is reduced')
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')
    } finally {
      media.restore()
    }
  })

  it('keeps the stage bar’s information when the motion is reduced', () => {
    const media = stubMatchMedia(false)
    try {
      render(
        <>
          <MotionPreference />
          <StageFeedbackBar plan={PLAN} state={STATE} />
        </>,
      )

      fireEvent.change(screen.getByLabelText('Motion'), { target: { value: 'reduced' } })
      expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')

      // The phase is said in the live region...
      const bar = screen.getByRole('group', { name: 'Workbench stage feedback' })
      expect(within(bar).getByRole('status')).toHaveTextContent(
        'Current phase: Locate (in progress)',
      )

      // ...and said in the structure, on the segment itself.
      const locate = bar.querySelector('.stage-bar__phase[data-stage="locate"]')
      expect(locate).not.toBeNull()
      expect(locate?.getAttribute('data-status')).toBe('active')
      expect(locate).toHaveTextContent('Locate')
      expect(locate).toHaveTextContent('in progress')
    } finally {
      media.restore()
    }
  })
})
