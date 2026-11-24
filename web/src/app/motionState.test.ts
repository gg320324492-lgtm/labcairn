import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  MOTION_ATTRIBUTE,
  MOTION_STORAGE_KEY,
  applyMotionState,
  effectiveMotion,
  readMotionChoice,
  writeMotionChoice,
} from './motionState'

/**
 * The motion state, away from the screen.
 *
 * **What is checked here is what the preference is and where it lives.** The
 * default follows the system; an explicit choice stands the motion down
 * whatever the system says; the choice is remembered across a reload and
 * only a choice the reader actually made is written; and a browser that
 * refuses to store it is reported rather than pretended away.
 *
 * **The preference is not the session token.** `api/session.ts` keeps the
 * token out of the browser's storage because a stored secret is a secret a
 * later change to this page could read out of the browser and send
 * somewhere. A motion preference is not a secret — it grants nothing and
 * names nobody — so it may be stored, and the key it is stored under is the
 * preference's own.
 */

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  localStorage.clear()
})

/** A storage that refuses every write, as a locked-down browser's does. */
function refusingStorage(): Storage {
  const refuse = (): never => {
    throw new Error('this browser refuses to store anything')
  }
  return {
    getItem: () => null,
    setItem: refuse,
    removeItem: refuse,
    clear: refuse,
    key: () => null,
    length: 0,
  }
}

describe('the motion preference', () => {
  it('is absent until the reader chooses one', () => {
    expect(readMotionChoice()).toBeNull()
  })

  it('is remembered across a reload', () => {
    expect(writeMotionChoice('reduced')).toBe(true)

    // A reload is a fresh read of the same storage: the choice is still there.
    expect(readMotionChoice()).toBe('reduced')
  })

  it('is stored under the preference’s own key', () => {
    writeMotionChoice('reduced')

    expect(localStorage.getItem(MOTION_STORAGE_KEY)).toBe('reduced')
  })

  it('does not store the default, so the system keeps deciding', () => {
    // Nothing is written at load: a stored "follow the system" would freeze
    // the answer at the moment of the first visit.
    expect(readMotionChoice()).toBeNull()
    expect(localStorage.length).toBe(0)
  })

  it('is read as no choice when what is stored is not a choice', () => {
    localStorage.setItem(MOTION_STORAGE_KEY, 'sideways')

    expect(readMotionChoice()).toBeNull()
  })

  it('is read as no choice when the browser refuses to be read', () => {
    expect(readMotionChoice(refusingStorage())).toBeNull()
  })

  it('says so when the browser refuses to remember it', () => {
    expect(writeMotionChoice('reduced', refusingStorage())).toBe(false)
  })

  it('is remembered by a browser that allows it', () => {
    expect(writeMotionChoice('reduced')).toBe(true)
  })
})

describe('the effective motion', () => {
  it('follows the system when the reader has chosen nothing', () => {
    expect(effectiveMotion(null, false)).toBe('full')
    expect(effectiveMotion(null, true)).toBe('reduced')
  })

  it('follows the system when the reader has chosen the system', () => {
    expect(effectiveMotion('system', false)).toBe('full')
    expect(effectiveMotion('system', true)).toBe('reduced')
  })

  it('is reduced when the reader has asked for it, whatever the system says', () => {
    expect(effectiveMotion('reduced', false)).toBe('reduced')
    expect(effectiveMotion('reduced', true)).toBe('reduced')
  })
})

describe('the motion state on the document', () => {
  it('is stated on the root, where the stylesheet reads it', () => {
    applyMotionState('reduced')

    expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('reduced')
  })

  it('is stated even when the motion is on', () => {
    applyMotionState('full')

    expect(document.documentElement.getAttribute(MOTION_ATTRIBUTE)).toBe('full')
  })
})
