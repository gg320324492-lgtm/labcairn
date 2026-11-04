/**
 * The workbench's reading of the event stream.
 *
 * **The events held here are the service's events, verbatim.** The hook
 * merges pages by `seq` because a reconnect can deliver a page that
 * overlaps what was already drawn — the service resumes *after* a cursor,
 * so the overlap is normally empty, but a page read twice is a page read
 * twice and the screen should show each event once. Nothing is derived,
 * nothing is reordered by anything but the service's own `seq`, and the
 * list is bounded so a long-running task does not grow the page without
 * limit.
 *
 * **The connection's state is part of what the panel draws.** It is not an
 * error the page can swallow: a reader that kept showing old events after
 * the stream died would be showing a stopped clock. The hook reports
 * `connecting`, `live`, `reconnecting` (with the failure's own words and
 * which attempt this is) and `disconnected` (with the last failure and a
 * way back).
 *
 * **`retry` starts a new generation, and the effect owns the old one.** The
 * generation is the effect's dependency, so bumping it aborts the old
 * reader and starts a new one; the events already read are kept, because
 * the new reader resumes at the cursor the old one reached only if the
 * service still has them — and a panel that threw away what it had before
 * reconnecting would ask a reader to remember what the screen forgot.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import { followEvents } from '../api/events'
import type { EventStreamState } from '../api/events'
import type { Event } from '../api/generated'

/** How many events the panel keeps. Older events are dropped from the list. */
const KEPT_EVENTS = 200

/** What the event panel draws. */
export interface EventStreamView {
  /** The events read so far, oldest first. */
  readonly events: readonly Event[]
  /** What the reader knows about its connection. */
  readonly state: EventStreamState
  /** Start a new reader, keeping the events already read. */
  readonly retry: () => void
}

/** How a test, or a slow machine, asks the reader to behave. */
export interface UseEventStreamOptions {
  /** Delay before a reconnect; zero in tests so a retry needs no clock. */
  readonly retryMs?: number
  /** Consecutive failures before the panel says it is disconnected. */
  readonly maxAttempts?: number
  /** The service's own polling pace while following. */
  readonly pollSeconds?: number
}

/** The old list with the new page merged in, or the old list unchanged. */
function merge(held: readonly Event[], arrived: readonly Event[]): readonly Event[] {
  const newest = held.length === 0 ? 0 : (held[held.length - 1]?.seq ?? 0)
  if (arrived.every((event) => event.seq <= newest)) {
    return held
  }
  const bySeq = new Map<number, Event>()
  for (const event of held) {
    bySeq.set(event.seq, event)
  }
  for (const event of arrived) {
    bySeq.set(event.seq, event)
  }
  return [...bySeq.values()].sort((left, right) => left.seq - right.seq).slice(-KEPT_EVENTS)
}

export function useEventStream(options: UseEventStreamOptions = {}): EventStreamView {
  const { retryMs, maxAttempts, pollSeconds } = options
  const [events, setEvents] = useState<readonly Event[]>([])
  const [state, setState] = useState<EventStreamState>({ kind: 'connecting' })
  const [generation, setGeneration] = useState(0)
  const cursor = useRef(0)
  const retry = useCallback(() => {
    // The state change belongs to the click and not to the effect: an effect
    // that sets state on the way in re-renders the page before the stream has
    // done anything, and the lint rule that says so is right.
    setState({ kind: 'connecting' })
    setGeneration((value) => value + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void followEvents(
      api,
      {
        onPage: (page) => {
          cursor.current = page.next_after_seq
          setEvents((held) => merge(held, page.events))
        },
        onState: setState,
      },
      {
        signal: controller.signal,
        startAfter: cursor.current,
        ...(retryMs === undefined ? {} : { retryMs: () => retryMs }),
        ...(maxAttempts === undefined ? {} : { maxAttempts }),
        ...(pollSeconds === undefined ? {} : { pollSeconds }),
      },
    )
    return () => {
      controller.abort()
    }
  }, [generation, retryMs, maxAttempts, pollSeconds])

  return { events, state, retry }
}
