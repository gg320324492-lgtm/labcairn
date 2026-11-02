import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import type { Event } from '../api/generated'
import { eventPage, FakeApi, sseFrame, TASK_ID } from '../test/fakeApi'
import { EventsView } from './EventsView'

/**
 * The events panel, driven through the network boundary.
 *
 * The fake answers the stream the way the service does — pages in
 * server-sent frames, a cursor on each page, and a body that can be held
 * open or closed — so what is checked here is the panel's reading and its
 * connection reporting, not a made-up list of events.
 */

let fake: FakeApi

beforeEach(() => {
  fake = new FakeApi()
  vi.stubGlobal('fetch', fake.fetch)
  forgetSessionToken()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

/** One event, with just the fields the panel draws. */
function event(seq: number, type: Event['type'] = 'task_created'): Event {
  return {
    seq,
    task_id: TASK_ID,
    type,
    occurred_at: '2026-10-20T08:00:00+00:00',
  }
}

/** The URLs the stream was opened with, most recent last. */
function streamUrls(): string[] {
  return fake.requests
    .map((request) => request.url.replace(/^\/api/, ''))
    .filter((url) => url.startsWith('/events/stream'))
}

describe('the events panel', () => {
  it('draws the events the service sent, and says the stream is live', async () => {
    fake.events = [
      event(1),
      { ...event(2, 'task_revised'), transition: { from_state: 'entered', to_state: 'completed' } },
    ]
    render(<EventsView />)

    expect(await screen.findByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('task_revised')).toBeInTheDocument()
    expect(screen.getByText(/entered.*completed/)).toBeInTheDocument()
    expect(
      await screen.findByText(/The event stream is live; the last event read is #2/),
    ).toBeInTheDocument()
    expect(streamUrls()).toHaveLength(1)
    expect(streamUrls()[0] ?? '').toContain('after_seq=0')
  })

  it('resumes from the cursor after a disconnect, and draws no event twice', async () => {
    fake.streamScript = [
      { frames: [sseFrame(eventPage([event(1)]))] },
      { frames: [sseFrame(eventPage([event(1), event(2, 'task_revised')]))], hold: true },
    ]
    render(<EventsView retryMs={0} />)

    expect(await screen.findByText('#2')).toBeInTheDocument()
    // The second attempt asked for what came after event 1, and the overlap
    // the fake sent anyway was merged rather than drawn twice.
    await waitFor(() => {
      expect(streamUrls()).toHaveLength(2)
    })
    expect(streamUrls()[1] ?? '').toContain('after_seq=1')
    expect(screen.getAllByText('#1')).toHaveLength(1)
    expect(
      screen.getByText(/The event stream is live; the last event read is #2/),
    ).toBeInTheDocument()
  })

  it('says it is disconnected rather than showing a stopped clock, and can reconnect', async () => {
    fake.streamScript = [
      { status: 503 },
      { status: 503 },
      { status: 503 },
      { frames: [sseFrame(eventPage([event(7)]))], hold: true },
    ]
    render(<EventsView retryMs={0} maxAttempts={3} />)

    expect(
      await screen.findByText(/The event stream is disconnected after 3 attempts/),
    ).toBeInTheDocument()
    // The failure is the service's own words, not a generic "offline".
    expect(screen.getByText(/the fake event stream refused attempt 3/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reconnect' }))

    expect(await screen.findByText('#7')).toBeInTheDocument()
    expect(await screen.findByText(/The event stream is live/)).toBeInTheDocument()
    expect(fake.streamAttempts).toBe(4)
  })

  it('keeps what it read when the connection is lost', async () => {
    fake.streamScript = [
      { frames: [sseFrame(eventPage([event(1)]))], hold: true },
      { frames: [sseFrame(eventPage([event(1), event(2)]))], hold: true },
    ]
    render(<EventsView retryMs={0} />)
    await screen.findByText('#1')

    // The service drops the connection; the reader reconnects and the panel
    // still shows the event it read before, beside the one it read after.
    expect(fake.closeStream()).toBe(true)
    expect(await screen.findByText('#2')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(streamUrls()[1] ?? '').toContain('after_seq=1')
  })

  it('waits on the service rather than inventing an empty log', async () => {
    render(<EventsView />)

    expect(
      await screen.findByText('The service has reported no event for this task.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/#\d+/)).not.toBeInTheDocument()
    // The panel is live with nothing to draw: an empty list is the service's
    // answer and not the page's guess.
    expect(
      screen.getByText(/The event stream is live; the service has sent no event/),
    ).toBeInTheDocument()
  })
})
