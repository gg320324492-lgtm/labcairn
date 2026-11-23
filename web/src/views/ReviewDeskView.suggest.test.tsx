import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi } from '../test/fakeApi'
import { ReviewDeskView } from './ReviewDeskView'

/**
 * The desk's suggestion loop, tested against a fake of the local API at the
 * network boundary.
 *
 * **The fake answers `fetch`, so the client, the paths, the session scheme
 * and the panel are all the real thing.** What is checked here is the loop's
 * three states as the work order states them: a run's own account drawn on
 * the desk, a refused real run shown with its reason and its substitute
 * fallback, and a failed run shown with retry and substitute entries. The
 * default is checked too: the desk starts in substitute mode, the mode that
 * spends nothing and sends nothing out of the machine.
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

/** The run button, by either of its two names — idle, or in flight. */
function runButton(): HTMLButtonElement {
  return screen.getByRole('button', { name: /Run suggestion loop|Asking…/ })
}

/** The body the client sent to `/review/suggest`, as the fake received it. */
function suggestBodies(): Array<Record<string, unknown>> {
  return fake.requests
    .filter((request) => request.method === 'POST' && request.url.includes('/review/suggest'))
    .map((request) => JSON.parse(request.body ?? '{}') as Record<string, unknown>)
}

describe('the review desk suggestion loop', () => {
  it('defaults to substitute mode, and the run the desk starts says so', async () => {
    render(<ReviewDeskView />)

    const substitute = screen.getByRole('radio', { name: /substitute/ })
    expect(substitute).toBeChecked()
    expect(screen.getByRole('radio', { name: /real model/ })).not.toBeChecked()

    fireEvent.click(runButton())

    await waitFor(() => {
      expect(fake.suggestionRuns).toBe(1)
    })
    const body = suggestBodies()[0] ?? {}
    expect(body.mode).toBe('substitute')
    expect(body.project_id).toBe('proj-lc-p4-cap')
    expect(body.version_id).toBe('ver-baseline-04')
  })

  it('draws the run record as counts and reasons, not request text', async () => {
    render(<ReviewDeskView />)

    fireEvent.click(runButton())

    const record = await screen.findByLabelText('Suggestion run record')
    expect(record).toHaveTextContent('Mode')
    expect(record).toHaveTextContent('substitute')
    expect(record).toHaveTextContent('substitute-model')
    expect(record).toHaveTextContent('Suggestions recorded')
    expect(record).toHaveTextContent('4')
    // A completed run names no stop condition, and the desk says so in words
    // rather than leaving the field blank.
    expect(record).toHaveTextContent('nothing — every pending opinion was walked')
    // The record is the account; the opinions are read again after the run.
    await waitFor(() => {
      expect(fake.requests.some((request) => request.url.includes('/review/opinions'))).toBe(true)
    })
  })

  it('shows a budget stop with its own words when the run stopped early', async () => {
    fake.suggestionRun = {
      ...fake.suggestionRun,
      stopped_reason: 'request_budget',
      requests_made: 3,
      suggestions_recorded: 3,
      opinions_skipped: 1,
    }
    render(<ReviewDeskView />)

    fireEvent.click(runButton())

    const record = await screen.findByLabelText('Suggestion run record')
    expect(record).toHaveTextContent('request budget reached')
    expect(record).toHaveTextContent('Opinions skipped')
    expect(record).toHaveTextContent('1')
  })

  it('shows the no-provider refusal with its reason, and offers the substitute', async () => {
    fake.suggestionOutcome = 'no_provider'
    render(<ReviewDeskView />)

    fireEvent.click(screen.getByRole('radio', { name: /real model/ }))
    fireEvent.click(runButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The service refused the real run')
    expect(alert).toHaveTextContent('model_suggestion_no_provider')
    expect(alert).toHaveTextContent(/no real-model transport is wired into this service/)
    // A refused real run offers the substitute, and no retry of the same
    // mode — the service said no, and asking again the same way is not a way
    // out.
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Switch to substitute' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'Switch to substitute' }))

    await waitFor(() => {
      expect(fake.suggestionRuns).toBe(2)
    })
    expect((suggestBodies()[1] ?? {}).mode).toBe('substitute')
    // The mode choice follows the switch, so the next run is the substitute's.
    expect(screen.getByRole('radio', { name: /substitute/ })).toBeChecked()
    await screen.findByLabelText('Suggestion run record')
  })

  it('shows a failed run with its reason, and offers retry and substitute', async () => {
    fake.suggestionOutcome = 'failure'
    render(<ReviewDeskView />)

    fireEvent.click(runButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The suggestion run failed')
    expect(alert).toHaveTextContent(/could not be reached/)
    // A failed run keeps both ways out: try the same mode again, or fall
    // back to the one that costs nothing.
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Switch to substitute' })).toBeEnabled()
    expect(screen.queryByLabelText('Suggestion run record')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => {
      expect(fake.suggestionRuns).toBe(2)
    })
    expect((suggestBodies()[1] ?? {}).mode).toBe('substitute')
  })

  it('stands the run button down while a run is in flight', async () => {
    render(<ReviewDeskView />)

    fireEvent.click(runButton())
    expect(runButton()).toBeDisabled()
    expect(runButton()).toHaveTextContent('Asking…')

    await screen.findByLabelText('Suggestion run record')
    expect(runButton()).toBeEnabled()
  })
})
