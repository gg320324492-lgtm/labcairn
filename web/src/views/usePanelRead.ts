/**
 * A panel's own read of the service.
 *
 * **Why these panels read for themselves.** The workbench's batch read
 * carries no parameters, and two of these panels cannot use one: the
 * trajectory's second read depends on the first one's answer — the
 * versions a project holds are asked about **by name**, and the names come
 * from the comments the first read returned — and the rules' list has to be
 * read again after the panel's own write, because the write's answer is one
 * rule and the list is what the panel draws.
 *
 * **What the rule is, though, is the workbench's own.** What is on the
 * screen is the API's answer, read again rather than remembered: the read
 * is scheduled by the effect, the answer is held verbatim, and nothing is
 * merged, derived or decided here. A panel that decided what the service
 * answered would be a second source of truth, and a change to the API would
 * not reach it.
 *
 * **Four states, and the first one is the panel's own.** A panel with no
 * question to ask has neither failed nor landed, and the frame's own
 * vocabulary has no word for it — so `idle` is said in the panel's words,
 * not in the service's. The other three are the frame's: a read in flight,
 * an answer, and a failure with the service's reason.
 */

import { useCallback, useEffect, useState } from 'react'

import { api, describeError } from '../api/client'
import type { ApiError } from '../api/client'
import type { ApiRead } from '../app/useWorkbench'

/** What a panel's read knows. */
export type PanelRead<T> =
  /** The panel has no question to ask yet. */
  | { readonly kind: 'idle' }
  /** The panel asked, and the service has not answered yet. */
  | { readonly kind: 'pending' }
  /** The service answered. */
  | { readonly kind: 'answered'; readonly data: T }
  /** The service did not answer, and this is why. */
  | { readonly kind: 'failed'; readonly error: ApiError }

/** A panel's read, and the way to ask again. */
export interface PanelReading<T> {
  /** What the read knows. */
  readonly read: PanelRead<T>
  /**
   * Ask the service again.
   *
   * Called after something has changed — a write the panel made, or a
   * question the caller changed. The read happens on the next effect, so
   * what the screen shows afterwards is the database's state and not the
   * page's memory of the call.
   */
  readonly again: () => void
}

/** What the last answer was, and which question it answered. */
interface Settled<T> {
  /** The question the answer belongs to: the path and the asking. */
  readonly key: string
  /** The answer, or why there is none. */
  readonly answer:
    | { readonly kind: 'answered'; readonly data: T }
    | { readonly kind: 'failed'; readonly error: ApiError }
    | null
}

/**
 * The read in the shape the panels draw it.
 *
 * The frame knows three things: it failed, it has not landed, or it has an
 * answer. **The idle state is not one of them**, and this helper does not
 * invent one: a panel with no question says so in its own words, and the
 * panel that has a question passes its own idle answer as the data.
 */
export function asApiRead<T>(read: PanelRead<T>): ApiRead<T> {
  if (read.kind === 'failed') {
    return { data: null, error: read.error }
  }
  return { data: read.kind === 'answered' ? read.data : null, error: null }
}

/**
 * Read one thing, and hold the answer.
 *
 * @param path the path to read, or null when the panel has no question to
 *   ask yet. A null path is not a failure and not an empty answer: it is
 *   the panel's own state, and the panel says it in its own words.
 */
export function usePanelRead<T>(path: string | null): PanelReading<T> {
  const [asking, setAsking] = useState(0)
  const [settled, setSettled] = useState<Settled<T>>({ key: '', answer: null })

  // The question the answer belongs to. The asking is in the key, so a
  // second read of the same path is a different question — and the answer
  // on hand stops being this one's.
  const key = path === null ? '' : `${path}#${asking}`

  useEffect(() => {
    if (path === null) {
      return
    }
    let live = true
    void api.get<T>(path).then(
      (data) => {
        if (live) {
          setSettled({ key, answer: { kind: 'answered', data } })
        }
      },
      (error: unknown) => {
        if (live) {
          setSettled({ key, answer: { kind: 'failed', error: describeError(error) } })
        }
      },
    )
    return () => {
      live = false
    }
    // The key carries the path, and the path is the only thing the read
    // depends on. No dependency list of its own: the read is scheduled by
    // the question, not by a change in anything else.
  }, [key, path])

  const again = useCallback(() => {
    setAsking((count) => count + 1)
  }, [])

  const read: PanelRead<T> =
    path === null
      ? { kind: 'idle' }
      : settled.key !== key
        ? { kind: 'pending' }
        : settled.answer === null
          ? { kind: 'pending' }
          : settled.answer.kind === 'failed'
            ? { kind: 'failed', error: settled.answer.error }
            : { kind: 'answered', data: settled.answer.data }

  return { read, again }
}
