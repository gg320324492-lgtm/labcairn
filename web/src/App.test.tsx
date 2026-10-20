import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { forgetSessionToken } from './api/session'
import { FakeApi } from './test/fakeApi'

/**
 * The shell.
 *
 * The workbench's own behaviour is checked in `app/workbench.test.tsx`,
 * which goes through the same network boundary; this file checks only that
 * the shell is the workbench and that it stands on its own.
 */

beforeEach(() => {
  vi.stubGlobal('fetch', new FakeApi().fetch)
  forgetSessionToken()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('is the workbench', () => {
    render(<App />)

    expect(screen.getByRole('main')).toHaveClass('workbench')
  })

  it('says what it is', async () => {
    render(<App />)

    expect(await screen.findByText(/This page talks to the local API/)).toBeInTheDocument()
  })
})
