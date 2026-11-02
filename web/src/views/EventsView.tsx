/**
 * The task's events, as the service reports them.
 *
 * **Why this panel exists.** The work order's carried limitation says *the
 * event stream is not consumed by the UI*. The stream is the service's
 * account of what happened, and until this panel the workbench drew only the
 * task as it stands — so a change that altered the event log alone was
 * invisible here.
 *
 * **What it draws, and what it refuses to draw.** Each row is one event the
 * service sent: its `seq`, its `type`, and the transition when it has one.
 * The panel does not interpret the payload and does not derive a story from
 * the sequence; the service's events are facts about what happened, and a
 * second telling of them here would be a second source of truth.
 *
 * **A disconnect is shown, not swallowed.** The line above the list says
 * whether the reader is connected, reconnecting, or has given up, and in the
 * last case it offers the way back. A panel that kept drawing its last page
 * while the stream was dead would be a stopped clock with a working face.
 *
 * **The cursor is visible.** The status line names the last event read, which
 * is the number the reader resumes from; a reader who wants to know whether
 * an event is missing can see where the panel has got to.
 */

import { useId } from 'react'
import type { JSX } from 'react'

import type { EventStreamState } from '../api/events'
import type { Event } from '../api/generated'
import { useEventStream } from '../app/useEventStream'
import { RecordList } from './Panel'

interface EventsViewProps {
  /** How long a reconnect waits; zero in tests so nothing depends on a clock. */
  readonly retryMs?: number
  /** Consecutive failures before the panel says it is disconnected. */
  readonly maxAttempts?: number
}

/** What the connection line says, in the panel's words. */
function statusLine(state: EventStreamState, events: readonly Event[]): string {
  const last = events.length === 0 ? null : (events[events.length - 1]?.seq ?? null)
  switch (state.kind) {
    case 'connecting':
      return 'Connecting to the event stream…'
    case 'live':
      return last === null
        ? 'The event stream is live; the service has sent no event for this task yet.'
        : `The event stream is live; the last event read is #${last}.`
    case 'reconnecting':
      return (
        `The event stream was interrupted (attempt ${state.attempt}): ${state.error.message} ` +
        (last === null
          ? 'Resuming from the beginning of the log.'
          : `Resuming after event #${last}.`)
      )
    case 'disconnected':
      return (
        `The event stream is disconnected after ${state.attempt} attempts: ${state.error.message} ` +
        (last === null
          ? 'No event was read before the connection was lost.'
          : `The ${events.length} event(s) read up to #${last} are still shown, and the list is not being updated.`)
      )
  }
}

export function EventsView({ retryMs, maxAttempts }: EventsViewProps): JSX.Element {
  const headingId = useId()
  const { events, state, retry } = useEventStream({
    ...(retryMs === undefined ? {} : { retryMs }),
    ...(maxAttempts === undefined ? {} : { maxAttempts }),
  })
  const disconnected = state.kind === 'disconnected'
  return (
    <section className="panel" aria-labelledby={headingId}>
      <h2 className="panel__title" id={headingId}>
        Events
      </h2>
      <p className="panel__note">
        The service&rsquo;s own account of what happened to this task, read from its event stream.
        The stream carries events and never commands, so a reconnect asks for what it missed and
        cannot ask for anything to be done.
      </p>
      <p className={disconnected ? 'panel__error' : 'panel__status'} role="status">
        {statusLine(state, events)}
      </p>
      {disconnected ? (
        <p className="workbench__actions">
          <button className="button" type="button" onClick={retry}>
            Reconnect
          </button>
        </p>
      ) : null}
      {events.length === 0 ? (
        <p className="panel__status">The service has reported no event for this task.</p>
      ) : (
        <RecordList>
          {events.map((event) => (
            <li className="record" key={event.seq}>
              <span className="record__key">#{event.seq}</span>
              <span className="record__name">{event.type}</span>
              {event.transition !== undefined && event.transition !== null ? (
                <span className="record__detail">
                  {event.transition.from_state} &rarr; {event.transition.to_state}
                </span>
              ) : null}
              {event.occurred_at !== undefined ? (
                <span className="record__detail">{event.occurred_at}</span>
              ) : null}
            </li>
          ))}
        </RecordList>
      )}
    </section>
  )
}
