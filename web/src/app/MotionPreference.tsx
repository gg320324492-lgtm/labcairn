/**
 * The motion preference: the entry point for reducing the workbench's motion.
 *
 * **What this control is.** The plan's §6.3 asks that a configurable entry
 * point for reducing motion be preserved, and this is it: a reader can turn
 * the workbench's transitions down from inside the product, whether or not
 * their system asks for it. The system-level path — the stylesheet's
 * `prefers-reduced-motion` media query — was already there; this control is
 * the application's own path, and the two stand the same motion down on the
 * same selectors.
 *
 * **What it offers, and what it does not.** The choice is between following
 * the system and reducing the motion, and there is no third option that adds
 * motion back: a reader whose system asks for reduced motion keeps it, and
 * the page does not pretend otherwise. The default is to follow the system,
 * so a reader who touches nothing gets what their machine already asked for.
 *
 * **The state is said twice, like every other state here.** The sentence
 * beside the control says in words what the workbench is doing, and the
 * document root carries the same fact as `data-motion` for the stylesheet to
 * read. Turning the motion down changes the decoration and nothing else: the
 * stage bar still names the phase in its live region and still carries it in
 * its attributes, because the motion was never the information.
 *
 * **What the control is not.** It is not a preference of the task, and it
 * asks the service for nothing: the workbench's motion is a property of the
 * page, and the page is the only thing it changes.
 */

import { useEffect, useId, useLayoutEffect, useState } from 'react'
import type { ChangeEvent, JSX } from 'react'

import {
  applyMotionState,
  effectiveMotion,
  readMotionChoice,
  reducedMotionQuery,
  writeMotionChoice,
} from './motionState'
import type { MotionChoice, MotionState } from './motionState'

/** What each choice is called on the control. */
const CHOICE_LABELS: Readonly<Record<MotionChoice, string>> = {
  system: 'Match the system',
  reduced: 'Reduce motion',
}

/**
 * The sentence that says what the workbench's motion is doing.
 *
 * **It says which path decided.** A reader who reduced the motion here and a
 * reader whose system asked for it are in the same state and did not get
 * there the same way, and the sentence names the way — otherwise the reader
 * would have to guess whether their choice was the one that took effect.
 */
function stateSentence(choice: MotionChoice | null, state: MotionState): string {
  if (state === 'full') {
    return 'Motion is on — the system does not ask for less, and this page follows it.'
  }
  if (choice === 'reduced') {
    return 'Motion is reduced — you asked this page to stand its transitions down.'
  }
  return 'Motion is reduced — the system asks for less, and this page follows it.'
}

export function MotionPreference(): JSX.Element {
  const fieldId = useId()
  const [choice, setChoice] = useState<MotionChoice | null>(() => readMotionChoice())
  const [systemReduced, setSystemReduced] = useState<boolean>(
    () => reducedMotionQuery()?.matches ?? false,
  )
  const [remembered, setRemembered] = useState<boolean>(true)

  // The system's answer can move while the page is open — a reader who turns
  // the setting on in their system's settings expects this page to follow —
  // so the page listens. The listener always listens; when the reader has
  // chosen "reduce motion" the system's answer changes nothing, because the
  // motion is already down.
  useEffect(() => {
    const list = reducedMotionQuery()
    if (list === null) {
      return
    }
    const onChange = (event: MediaQueryListEvent): void => {
      setSystemReduced(event.matches)
    }
    list.addEventListener('change', onChange)
    return () => {
      list.removeEventListener('change', onChange)
    }
  }, [])

  const state = effectiveMotion(choice, systemReduced)

  // The attribute is set before the browser paints, so the page's motion is
  // the decided motion from the first frame rather than from the first
  // effect.
  useLayoutEffect(() => {
    applyMotionState(state)
  }, [state])

  const onChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    const next: MotionChoice = event.target.value === 'reduced' ? 'reduced' : 'system'
    setChoice(next)
    setRemembered(writeMotionChoice(next))
  }

  return (
    <p className="motion">
      <label className="motion__label" htmlFor={fieldId}>
        Motion
      </label>
      <select
        id={fieldId}
        className="motion__choice"
        value={choice ?? 'system'}
        onChange={onChange}
      >
        {(['system', 'reduced'] as const).map((option) => (
          <option key={option} value={option}>
            {CHOICE_LABELS[option]}
          </option>
        ))}
      </select>
      <span className="motion__state" role="status">
        {stateSentence(choice, state)}
      </span>
      {remembered ? null : (
        <span className="motion__note">
          This browser refused to remember the choice; it lasts until this page is closed.
        </span>
      )}
    </p>
  )
}
