/**
 * Following the service's event stream.
 *
 * **The stream carries facts, and this reader treats it that way.** Each
 * frame is one `EventStreamPage` — the same page `GET /events` answers with —
 * so the reader has no vocabulary of its own: it parses the frame the
 * service sends, hands the page on, and moves its cursor to
 * `next_after_seq`. It cannot ask the service to do anything, because the
 * page has no field in which a command could travel.
 *
 * **A disconnect is a state, not an exception for the caller to swallow.**
 * Every failure is reported through `onState`, with the service's own reason
 * when the service gave one, and the reader resumes from the cursor it last
 * saw. A stream that died silently would leave a panel showing old events
 * while the work moved on — the panel would look alive and be lying, which
 * is the failure mode this module exists to make visible.
 *
 * **The cursor survives the reconnect, and that is what makes the resume
 * gapless.** `after_seq` is the number the last page ended at, so events
 * appended while the connection was down are read on the next attempt and
 * events already drawn are not drawn twice. When nothing has been read yet
 * the cursor is zero, which is where the service's log begins.
 *
 * **The parser is deliberately small.** Server-sent events are lines of the
 * form `data: <text>`, frames separated by a blank line, with `:` comment
 * lines used as heartbeats. Only `data:` lines are read, joined by newlines
 * as the format says; everything else is ignored. A frame whose data is not
 * a page is skipped rather than thrown, because one malformed frame is not a
 * reason to stop reading the rest of the stream.
 */

import { ApiFailure, ApiRefusal, describeError, isRefusalBody } from './client'
import type { ApiError, LabCairnClient } from './client'
import type { EventStreamPage } from './generated'
import { eventsStreamPath } from './paths'

/** What the reader knows about its connection. */
export type EventStreamState =
  | { readonly kind: 'connecting' }
  | { readonly kind: 'live' }
  | {
      readonly kind: 'reconnecting'
      readonly attempt: number
      readonly error: ApiError
    }
  | {
      readonly kind: 'disconnected'
      readonly attempt: number
      readonly error: ApiError
    }

/** What the reader tells its caller. */
export interface EventStreamHandlers {
  /** One page the service sent. */
  readonly onPage: (page: EventStreamPage) => void
  /** Every change of the connection's state. */
  readonly onState: (state: EventStreamState) => void
}

/** How the reader is asked to behave. */
export interface FollowOptions {
  /** Stops the reader when aborted; also aborts the request in flight. */
  readonly signal?: AbortSignal
  /** How long to wait before attempt *n*; defaults to capped exponential. */
  readonly retryMs?: (attempt: number) => number
  /** Attempts before the reader gives up and says so. */
  readonly maxAttempts?: number
  /** How often the service should look for new events while following. */
  readonly pollSeconds?: number
  /**
   * Where to resume from when this reader starts.
   *
   * Zero for a fresh panel. A panel that has read events and is starting a
   * **new** reader — after a disconnect it chose to retry, rather than the
   * reader's own in-place reconnect — passes the cursor it reached, so the
   * new reader continues rather than beginning again.
   */
  readonly startAfter?: number
}

const DEFAULT_MAX_ATTEMPTS = 5

function defaultRetryMs(attempt: number): number {
  // One second, doubling, capped at ten: a service that has just refused a
  // connection is not helped by a request storm, and a person is not helped
  // by a two-minute silence.
  return Math.min(1000 * 2 ** (attempt - 1), 10_000)
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal?.aborted === true) {
      resolve()
      return
    }
    const timer = setTimeout(finish, ms)
    function finish(): void {
      clearTimeout(timer)
      signal?.removeEventListener('abort', finish)
      resolve()
    }
    signal?.addEventListener('abort', finish, { once: true })
  })
}

/** A frame's page, or null when the frame carries something else. */
function pageOf(frame: string): EventStreamPage | null {
  const data: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('data:')) {
      data.push(line.slice('data:'.length).replace(/^ /, ''))
    }
  }
  if (data.length === 0) {
    return null
  }
  try {
    const parsed: unknown = JSON.parse(data.join('\n'))
    if (typeof parsed !== 'object' || parsed === null) {
      return null
    }
    const candidate = parsed as { events?: unknown; next_after_seq?: unknown }
    if (!Array.isArray(candidate.events) || typeof candidate.next_after_seq !== 'number') {
      return null
    }
    return parsed as EventStreamPage
  } catch {
    return null
  }
}

/** Read every page a body carries, until it ends. */
async function readFrames(
  body: ReadableStream<Uint8Array>,
  onPage: (page: EventStreamPage) => void,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffered = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffered += decoder.decode(value, { stream: true })
      let boundary = buffered.indexOf('\n\n')
      while (boundary !== -1) {
        const page = pageOf(buffered.slice(0, boundary))
        buffered = buffered.slice(boundary + 2)
        if (page !== null) {
          onPage(page)
        }
        boundary = buffered.indexOf('\n\n')
      }
    }
    buffered += decoder.decode()
    const page = pageOf(buffered)
    if (page !== null) {
      onPage(page)
    }
  } finally {
    reader.releaseLock()
  }
}

/** What a non-ok stream response means, in the client's own error types. */
async function failureOf(response: Response): Promise<Error> {
  const payload: unknown = await response.json().catch(() => null)
  if (isRefusalBody(payload)) {
    return new ApiRefusal(payload)
  }
  return new ApiFailure(
    response.status,
    `the event stream answered ${response.status} ${response.statusText}.`,
    payload,
  )
}

/**
 * Follow the task's events until the caller stops or the attempts run out.
 *
 * The promise settles when the reader stops: on abort, or after
 * `maxAttempts` consecutive failures (with `disconnected` reported first).
 * It does not reject on a service failure — the failure is the state the
 * caller draws, and a rejected promise would be a second way to say the same
 * thing that a caller can forget to catch.
 */
export async function followEvents(
  client: LabCairnClient,
  handlers: EventStreamHandlers,
  options: FollowOptions = {},
): Promise<void> {
  const retryMs = options.retryMs ?? defaultRetryMs
  const maxAttempts = options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS
  let cursor = options.startAfter ?? 0
  let failures = 0
  let lastError: ApiError = { reason: null, message: 'the event stream has not connected yet.' }

  for (;;) {
    if (options.signal?.aborted === true) {
      return
    }
    handlers.onState(
      failures === 0
        ? { kind: 'connecting' }
        : { kind: 'reconnecting', attempt: failures, error: lastError },
    )
    try {
      const response = await client.stream(
        eventsStreamPath(cursor, options.pollSeconds),
        options.signal,
      )
      if (!response.ok || response.body === null) {
        throw await failureOf(response)
      }
      // The connection is up. The attempt count restarts here rather than
      // after the body ends, so a stream that delivers pages for an hour and
      // then drops is a first failure and not the sixth.
      failures = 0
      handlers.onState({ kind: 'live' })
      await readFrames(response.body, (page) => {
        cursor = page.next_after_seq
        handlers.onPage(page)
      })
      lastError = {
        reason: null,
        message: `the event stream closed after event ${cursor}; resuming from there.`,
      }
    } catch (error) {
      // `?? false` rather than `=== true`: the check at the top of the loop
      // narrows `aborted` to false for the rest of the body, and the signal
      // can have been aborted while the request was in flight.
      if (options.signal?.aborted ?? false) {
        return
      }
      lastError = describeError(error)
    }

    failures += 1
    if (failures >= maxAttempts) {
      handlers.onState({ kind: 'disconnected', attempt: failures, error: lastError })
      return
    }
    await wait(retryMs(failures), options.signal)
  }
}
